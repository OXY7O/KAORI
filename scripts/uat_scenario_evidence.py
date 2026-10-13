"""Manual KAORI UAT evidence dossier from existing pytest JUnit and artifact files.

No CI integration, Gherkin runner, provider mutation or human acceptance performed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_VARIANTS = ("large-desktop", "laptop", "compact-laptop", "tablet", "mobile", "small-mobile")
_OUTCOMES = frozenset({"PASS", "FAIL", "BLOCKED", "NOT RUN", "SKIP"})


def _node_key(classname: str, name: str) -> str:
    return f"{classname.replace('/', '.')}::{name}"


def read_junit(paths: list[Path]) -> dict[str, list[str]]:
    """Read actual JUnit testcase outcomes; duplicates/reruns never erase a failure."""
    cases: dict[str, list[str]] = {}
    for path in paths:
        root = ET.parse(path).getroot()  # noqa: S314 -- local user-selected JUnit artifacts
        for node in root.iter("testcase"):
            classname = str(node.get("classname") or "")
            name = str(node.get("name") or "")
            if not classname or not name:
                continue
            status = "PASS"
            if node.find("failure") is not None or node.find("error") is not None:
                status = "FAIL"
            elif node.find("skipped") is not None:
                status = "SKIP"
            cases.setdefault(_node_key(classname, name), []).append(status)
    return cases


def _test_outcomes(nodeid: str, variants: list[str], cases: dict[str, list[str]]) -> list[str]:
    path, name = nodeid.split("::", 1)
    classname = path.removesuffix(".py").replace("/", ".")
    # Pytest writes parametrized cases as name[large-desktop], etc.
    names = [f"{name}[{variant}]" for variant in variants] if variants else [name]
    expected = [_node_key(classname, item) for item in names]
    return [
        "NOT RUN" if key not in cases else (
            "FAIL" if "FAIL" in cases[key] else (
                "SKIP" if "SKIP" in cases[key] else "PASS"
            )
        )
        for key in expected
    ]


def _artifact_status(
    scenario: dict[str, Any], evidence: list[dict[str, Any]], root: Path,
    *, candidate: dict[str, Any], run: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    requirements = scenario.get("required_artifacts") or {}
    expected_keys = {
        f"{node['nodeid']}::{variant}"
        for node in scenario["nodes"]
        for variant in node.get("variants", [])
    }
    for kind, count in requirements.items():
        valid: set[str] = set()
        used_paths: set[Path] = set()
        for entry in evidence:
            if entry.get("kind") != kind:
                continue
            relative = entry.get("path")
            if not isinstance(relative, str) or not relative.strip():
                continue
            candidate = root / relative
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root.resolve()) or candidate.is_symlink():
                continue
            if not resolved.is_file() or resolved.stat().st_size == 0 or resolved in used_paths:
                continue
            if kind in {"provider_readback", "committed_state", "activity_audit"}:
                try:
                    document = json.loads(resolved.read_text(encoding="utf-8"))
                except (OSError, ValueError, UnicodeError):
                    continue
                if not isinstance(document, dict) or document.get("verified") is not True:
                    continue
                if (
                    document.get("source_sha") != candidate.get("source_sha")
                    or document.get("run_id") != run.get("run_id")
                ):
                    continue
            if expected_keys and kind in {"screenshot", "trace"}:
                nodeid = entry.get("nodeid")
                variant = entry.get("variant")
                key = f"{nodeid}::{variant}"
                if key not in expected_keys:
                    continue
                valid.add(key)
            else:
                valid.add(relative)
            used_paths.add(resolved)
        if len(valid) < count or (
            expected_keys and kind in {"screenshot", "trace"} and count == len(expected_keys)
            and not expected_keys.issubset(valid)
        ):
            missing.append(f"{kind}: {len(valid)}/{count} verified files")
    return missing


def evaluate(
    manifest: dict[str, Any],
    execution: dict[str, Any],
    cases: dict[str, list[str]],
    *,
    expected_source: str,
    expected_tree: str,
    expected_digest: str | None,
    evidence_root: Path,
) -> dict[str, Any]:
    candidate = execution.get("candidate") or {}
    run = execution.get("run") or {}
    env = execution.get("environment") or {}
    problems: list[str] = []
    for field in ("run_id", "runner"):
        if not isinstance(run.get(field), str) or not run[field].strip():
            problems.append(f"execution {field} missing")
    started_at = run.get("started_at")
    try:
        parsed = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            problems.append("execution started_at must include timezone")
    except ValueError:
        problems.append("execution started_at is not ISO-8601")
    for label, actual, expected in (
        ("source_sha", candidate.get("source_sha"), expected_source),
        ("tree_sha", candidate.get("tree_sha"), expected_tree),
    ):
        if not isinstance(actual, str) or not _SHA.fullmatch(actual):
            problems.append(f"{label} missing/invalid")
        elif actual != expected:
            problems.append(f"{label} mismatches the approved exact candidate")
    if not _SHA.fullmatch(expected_source) or not _SHA.fullmatch(expected_tree):
        raise ValueError("Expected source/tree must be 40 lowercase hexadecimal characters.")
    if env.get("kind") == "server_uat":
        if not expected_digest or not _DIGEST.fullmatch(expected_digest):
            raise ValueError("server_uat requires the approved OCI digest.")
    if expected_digest:
        if not _DIGEST.fullmatch(expected_digest):
            raise ValueError("Invalid approved OCI digest.")
        if candidate.get("oci_digest") != expected_digest:
            problems.append("OCI digest mismatches the deployed accepted candidate")
    if env.get("kind") not in {"local", "server_uat"}:
        problems.append("unknown/missing execution environment kind")
    if env.get("provider_mode") not in {"simulated", "real"}:
        problems.append("provider evidence mode missing/invalid")

    collected: list[dict[str, Any]] = []
    all_evidence = execution.get("evidence") or {}
    for scenario in manifest["scenarios"]:
        scenario_id = scenario["id"]
        outcomes = [
            status
            for node in scenario["nodes"]
            for status in _test_outcomes(node["nodeid"], node.get("variants", []), cases)
        ]
        evidence = all_evidence.get(scenario_id, [])
        evidence_errors = _artifact_status(
            scenario, evidence, evidence_root, candidate=candidate, run=run,
        )
        if problems:
            result = "BLOCKED"
        elif "FAIL" in outcomes:
            result = "FAIL"
        elif "SKIP" in outcomes:
            result = "SKIP"
        elif "NOT RUN" in outcomes:
            result = "NOT RUN"
        elif evidence_errors:
            result = "BLOCKED"
        elif scenario.get("real_provider_required") and (
            env.get("provider_mode") != "real" or env.get("kind") != "server_uat"
        ):
            result = "BLOCKED"
            evidence_errors.append("authorized real-provider server UAT evidence required")
        else:
            result = "PASS"
        assert result in _OUTCOMES
        collected.append({
            "id": scenario_id,
            "result": result,
            "test_cases": len(outcomes),
            "passed_test_cases": outcomes.count("PASS"),
            "evidence_gaps": evidence_errors,
            "test_nodes": [node["nodeid"] for node in scenario["nodes"]],
        })
    ready = not problems and bool(collected) and all(x["result"] == "PASS" for x in collected)
    return {
        "contract_version": 1,
        "run": {key: run.get(key) for key in ("run_id", "runner", "started_at")},
        "candidate": {key: candidate.get(key) for key in ("source_sha", "tree_sha", "oci_digest")},
        "environment": env,
        "identity_problems": problems,
        "coverage": {
            "required": len(collected),
            "machine_pass": sum(x["result"] == "PASS" for x in collected),
            "fail": sum(x["result"] == "FAIL" for x in collected),
            "blocked": sum(x["result"] == "BLOCKED" for x in collected),
            "not_run": sum(x["result"] == "NOT RUN" for x in collected),
            "skip": sum(x["result"] == "SKIP" for x in collected),
        },
        "scenarios": collected,
        "machine_readiness": "READY_FOR_HUMAN_REVIEW" if ready else "INCOMPLETE",
        "human_acceptance": "PENDING",
        "disclaimer": "Machine evidence is not authorized human UAT acceptance.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate exact-candidate KAORI UAT evidence.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--junit", type=Path, nargs="+", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--expected-digest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        execution = json.loads(args.execution.read_text(encoding="utf-8"))
        result = evaluate(
            manifest, execution, read_junit(args.junit),
            expected_source=args.expected_source,
            expected_tree=args.expected_tree,
            expected_digest=args.expected_digest,
            evidence_root=args.evidence_root,
        )
    except (OSError, ValueError, KeyError, ET.ParseError, TypeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Machine readiness: {result['machine_readiness']} — human acceptance PENDING")
    return 0 if result["machine_readiness"] == "READY_FOR_HUMAN_REVIEW" else 1


if __name__ == "__main__":
    sys.exit(main())
