#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # nosec B405
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

PROFILE_VERSION = '2'
FULL_GATE_NAMES = (
    'Static, Architecture, and Governance',
    'Secrets, SAST, Dependencies, and Workflow Security',
    'Functional and Integration Tests',
    'Frontend Reproducibility',
    'Production Image, Container Security, Runtime, and DAST',
)
SENSITIVE_PREFIXES = (
    '.github/workflows/',
    '.github/ci/',
    'requirements/',
    'migrations/',
    'scripts/ci_admission.py',
    'scripts/quality_gate.sh',
    'scripts/verify_',
    'tests/contracts/release/',
    'Dockerfile',
    'docker-compose',
)
PROFILE_DISPLAY = {
    'full': 'Full Admission',
    'pr-integration': 'PR Integration',
    'staging-integration': 'Staging Integration',
    'promotion': 'Promotion',
    'post-promotion': 'Post-promotion',
}
TEST_TAXONOMY_LABELS = (
    'Unit Tests',
    'Functional Tests',
    'Integration Tests',
    'Security Regression',
    'Rendering / UI',
    'Contract Tests',
    'Migration Tests',
    'End-to-End Smoke',
)


class ProfileDecision(NamedTuple):
    profile: str
    execution: str
    reason: str
    display_name: str


class ReuseDecision(NamedTuple):
    reusable: bool
    reason: str
    full_admission_run_id: int | None = None
    source_sha: str | None = None
    source_tree: str | None = None


def _is_sensitive(path: str) -> bool:
    normalized = path[2:] if path.startswith('./') else path
    return any(normalized == prefix or normalized.startswith(prefix) for prefix in SENSITIVE_PREFIXES)


def resolve_profile(
    *,
    event_name: str,
    ref: str,
    base_ref: str,
    head_ref: str,
    changed_paths: Sequence[str],
) -> ProfileDecision:
    if event_name == 'pull_request' and base_ref == 'kaori/staging':
        profile = 'pr-integration'
    elif event_name == 'pull_request' and base_ref == 'main' and head_ref == 'kaori/staging':
        profile = 'promotion'
    elif event_name == 'push' and ref == 'refs/heads/kaori/staging':
        profile = 'staging-integration'
    elif event_name == 'push' and ref == 'refs/heads/main':
        profile = 'post-promotion'
    else:
        profile = 'full'

    if profile == 'full':
        return ProfileDecision(
            profile, 'full', 'Implementation source trees require comprehensive validation.', PROFILE_DISPLAY[profile]
        )

    sensitive = sorted(path for path in changed_paths if _is_sensitive(path))
    if sensitive:
        return ProfileDecision(
            profile,
            'full',
            f'Sensitive validation-authority change requires Full Admission: {sensitive[0]}',
            PROFILE_DISPLAY[profile],
        )
    return ProfileDecision(profile, 'fast', 'Eligible for exact Admission evidence reuse.', PROFILE_DISPLAY[profile])


def evidence_reuse_decision(
    evidence: Mapping[str, Any],
    *,
    current_sha: str,
    current_tree: str,
    required_profile_version: str,
) -> ReuseDecision:
    if str(evidence.get('result', '')).upper() != 'PASS':
        return ReuseDecision(False, 'Full Admission evidence result is not PASS.')
    if str(evidence.get('profile_version', '')) != required_profile_version:
        return ReuseDecision(False, 'Validation profile version does not match current authority.')
    if str(evidence.get('source_sha', '')) != current_sha:
        return ReuseDecision(False, 'Source commit SHA does not match Admission evidence.')
    if str(evidence.get('source_tree', '')) != current_tree:
        return ReuseDecision(False, 'Source tree does not match Admission evidence.')

    gates = evidence.get('gates')
    if not isinstance(gates, Mapping):
        return ReuseDecision(False, 'Admission evidence does not contain required gate conclusions.')
    for gate in FULL_GATE_NAMES:
        conclusion = str(gates.get(gate, '')).lower()
        if conclusion != 'success':
            return ReuseDecision(False, f'{gate} is {conclusion or "missing"}; evidence is not reusable.')

    try:
        run_id = int(evidence.get('full_admission_run_id'))
    except (TypeError, ValueError):
        return ReuseDecision(False, 'Admission evidence is missing a valid Full Admission run ID.')
    return ReuseDecision(
        True, 'Exact successful Full Admission evidence is reusable.', run_id, current_sha, current_tree
    )


def staging_lineage_reuse_decision(
    *,
    parent_shas: Sequence[str],
    merge_tree: str,
    expected_staging_parent: str,
    admitted_head_sha: str,
    admitted_tree: str,
) -> ReuseDecision:
    if tuple(parent_shas) != (expected_staging_parent, admitted_head_sha):
        return ReuseDecision(False, 'Staging merge parents do not match the admitted lineage.')
    if merge_tree != admitted_tree:
        return ReuseDecision(False, 'Staging merge tree differs from the admitted source tree.')
    return ReuseDecision(
        True,
        'Staging parents and tree are equivalent to admitted lineage.',
        source_sha=admitted_head_sha,
        source_tree=admitted_tree,
    )


def promotion_lineage_reuse_decision(
    *,
    parent_shas: Sequence[str],
    merge_tree: str,
    expected_main_parent: str,
    accepted_staging_sha: str,
    accepted_tree: str,
) -> ReuseDecision:
    if tuple(parent_shas) != (expected_main_parent, accepted_staging_sha):
        return ReuseDecision(False, 'Promotion merge parents do not match the accepted staging lineage.')
    if merge_tree != accepted_tree:
        return ReuseDecision(False, 'Promotion tree differs from the UAT-accepted staging tree.')
    return ReuseDecision(
        True,
        'Promotion parents and tree preserve the accepted staging lineage.',
        source_sha=accepted_staging_sha,
        source_tree=accepted_tree,
    )


def render_operator_summary(
    *,
    result: str,
    profile: str,
    commit_sha: str,
    tree_sha: str,
    evidence: str,
    fresh_checks: Sequence[str],
    reused_coverage: Sequence[str],
    duration: str,
    first_failure: str | None,
    next_action: str,
    coverage_summary: str | None = None,
) -> str:
    normalized = result.upper()
    if normalized not in {'PASS', 'FAIL', 'SKIP', 'REUSED', 'FALLBACK'}:
        raise ValueError(f'Unsupported KAORI result vocabulary: {result}')
    lines = [
        f'## KAORI CI — {profile}',
        '',
        f'**Result:** {normalized}',
        f'**Profile:** {profile}',
        f'**Commit SHA:** `{commit_sha}`',
        f'**Tree SHA:** `{tree_sha}`',
        f'**Evidence:** {evidence}',
        f'**Duration:** {duration}',
        f'**Coverage summary:** {coverage_summary or "See grouped gate results below."}',
        f'**Fresh checks:** {", ".join(fresh_checks) if fresh_checks else "None"}',
        f'**Reused checks:** {", ".join(reused_coverage) if reused_coverage else "None"}',
    ]
    if first_failure and first_failure.strip().lower() not in {'none', 'n/a'}:
        lines.append(f'**First actionable failure:** {first_failure}')
    lines.extend((f'**Next action:** {next_action}', ''))
    return '\n'.join(lines)


def _testcase_taxonomy(testcase: ET.Element) -> str:
    file_path = str(testcase.attrib.get('file', '')).replace('\\', '/')
    class_path = str(testcase.attrib.get('classname', '')).replace('.', '/')
    evidence_path = f'{file_path} {class_path}'

    if 'tests/unit/' in evidence_path:
        return 'Unit Tests'
    if 'tests/integration/' in evidence_path:
        return 'Integration Tests'
    if 'tests/security/' in evidence_path:
        return 'Security Regression'
    if 'tests/rendering/' in evidence_path:
        return 'Rendering / UI'
    if 'tests/contracts/' in evidence_path:
        return 'Contract Tests'
    if 'tests/migrations/' in evidence_path:
        return 'Migration Tests'
    if 'tests/e2e/' in evidence_path:
        return 'End-to-End Smoke'
    return 'Functional Tests'


def _junit_outcome(testcase: ET.Element) -> str:
    if testcase.find('failure') is not None:
        return 'failed'
    if testcase.find('error') is not None:
        return 'error'
    if testcase.find('skipped') is not None:
        return 'skipped'
    return 'passed'


def _test_word(count: int) -> str:
    return 'test' if count == 1 else 'tests'


def render_test_taxonomy_summary(junit_paths: Sequence[Path]) -> str:
    counts = {
        label: {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0} for label in TEST_TAXONOMY_LABELS
    }
    for junit_path in junit_paths:
        # Inputs are trusted pytest JUnit files generated inside the current CI workspace.
        root = ET.parse(junit_path).getroot()  # nosec B314
        for testcase in root.iter('testcase'):
            label = _testcase_taxonomy(testcase)
            counts[label][_junit_outcome(testcase)] += 1

    lines: list[str] = []
    for label in TEST_TAXONOMY_LABELS:
        bucket = counts[label]
        passed = bucket['passed']
        failed = bucket['failed']
        errors = bucket['error']
        skipped = bucket['skipped']
        total = passed + failed + errors + skipped

        if failed or errors:
            details = [f'{failed} failed'] if failed else []
            if errors:
                details.append(f'{errors} error' if errors == 1 else f'{errors} errors')
            if passed:
                details.append(f'{passed} passed')
            if skipped:
                details.append(f'{skipped} skipped')
            lines.append(f'FAIL — KAORI {label} · {" / ".join(details)}')
        elif passed:
            detail = f'{total} {_test_word(total)}'
            if skipped:
                detail = f'{passed} passed / {skipped} skipped'
            lines.append(f'PASS — KAORI {label} · {detail}')
        elif skipped:
            lines.append(f'SKIP — KAORI {label} · {skipped} skipped')
        else:
            lines.append(f'SKIP — KAORI {label} · 0 tests')
    return '\n'.join(lines)


def build_full_evidence(
    *,
    source_sha: str,
    source_tree: str,
    run_id: int,
    run_attempt: int,
    workflow_ref: str,
    gates: Mapping[str, str],
) -> dict[str, Any]:
    return {
        'result': 'PASS',
        'profile': 'full',
        'profile_version': PROFILE_VERSION,
        'source_sha': source_sha,
        'source_tree': source_tree,
        'full_admission_run_id': run_id,
        'run_attempt': run_attempt,
        'workflow_ref': workflow_ref,
        'gates': dict(gates),
    }


def _validated_github_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'api.github.com':
        raise ValueError('KAORI CI Admission only permits HTTPS requests to api.github.com.')
    if parsed.username or parsed.password:
        raise ValueError('KAORI CI Admission does not permit credentials embedded in request URLs.')
    return parsed.geturl()


def _github_request(url: str, token: str, *, binary: bool = False) -> Any:
    request = urllib.request.Request(
        _validated_github_url(url),
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'KAORI-CI-Admission',
        },
    )
    # URL is validated above to HTTPS api.github.com with no embedded credentials.
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
        return response.read() if binary else json.load(response)


def _commit_metadata(repository: str, token: str, sha: str) -> tuple[str, tuple[str, ...]]:
    payload = _github_request(f'https://api.github.com/repos/{repository}/commits/{sha}', token)
    return str(payload['commit']['tree']['sha']), tuple(str(parent['sha']) for parent in payload.get('parents', ()))


def _candidate_lineage(repository: str, token: str, start_sha: str, max_depth: int = 4) -> list[tuple[str, str]]:
    queue: list[tuple[str, int]] = [(start_sha, 0)]
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []
    while queue:
        sha, depth = queue.pop(0)
        if sha in seen or depth > max_depth:
            continue
        seen.add(sha)
        tree, parents = _commit_metadata(repository, token, sha)
        candidates.append((sha, tree))
        ordered = list(parents[1:2]) + list(parents[:1]) + list(parents[2:])
        queue.extend((parent, depth + 1) for parent in ordered)
    return candidates


def find_remote_full_evidence(
    *,
    repository: str,
    token: str,
    workflow: str,
    start_sha: str,
    current_tree: str,
) -> ReuseDecision:
    encoded_workflow = urllib.parse.quote(workflow, safe='')
    for candidate_sha, candidate_tree in _candidate_lineage(repository, token, start_sha):
        if candidate_tree != current_tree:
            continue
        query = urllib.parse.urlencode({'head_sha': candidate_sha, 'status': 'success', 'per_page': 20})
        runs = _github_request(
            f'https://api.github.com/repos/{repository}/actions/workflows/{encoded_workflow}/runs?{query}', token
        ).get('workflow_runs', [])
        for run in runs:
            run_id = int(run['id'])
            artifacts = _github_request(
                f'https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts', token
            ).get('artifacts', [])
            for artifact in artifacts:
                if not str(artifact.get('name', '')).startswith('kaori-full-admission-'):
                    continue
                archive = _github_request(str(artifact['archive_download_url']), token, binary=True)
                with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                    if 'admission-evidence.json' not in bundle.namelist():
                        continue
                    evidence = json.loads(bundle.read('admission-evidence.json').decode('utf-8'))
                decision = evidence_reuse_decision(
                    evidence,
                    current_sha=candidate_sha,
                    current_tree=current_tree,
                    required_profile_version=PROFILE_VERSION,
                )
                if decision.reusable:
                    return decision
    return ReuseDecision(False, 'No exact successful Full Admission evidence was found in the source lineage.')


def _write_output(values: Mapping[str, str]) -> None:
    payload = ''.join(f'{key}={value}\n' for key, value in values.items())
    output_path = os.environ.get('GITHUB_OUTPUT')
    if output_path:
        with Path(output_path).open('a', encoding='utf-8') as stream:
            stream.write(payload)
    else:
        sys.stdout.write(payload)


def _route(args: argparse.Namespace) -> int:
    changed = (
        tuple(Path(args.changed_paths_file).read_text(encoding='utf-8').splitlines()) if args.changed_paths_file else ()
    )
    decision = resolve_profile(
        event_name=args.event_name,
        ref=args.ref,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_paths=changed,
    )
    _write_output(
        {
            'profile': decision.profile,
            'execution': decision.execution,
            'reason': decision.reason.replace('\n', ' '),
            'display_profile': decision.display_name,
        }
    )
    return 0


def _find_evidence(args: argparse.Namespace) -> int:
    decision = find_remote_full_evidence(
        repository=args.repository,
        token=args.token,
        workflow=args.workflow,
        start_sha=args.start_sha,
        current_tree=args.current_tree,
    )
    _write_output(
        {
            'reusable': 'true' if decision.reusable else 'false',
            'evidence_run_id': str(decision.full_admission_run_id or ''),
            'evidence_source_sha': decision.source_sha or '',
            'evidence_source_tree': decision.source_tree or '',
            'evidence_reason': decision.reason.replace('\n', ' '),
        }
    )
    return 0


def _write_evidence(args: argparse.Namespace) -> int:
    gates = {
        'Static, Architecture, and Governance': args.static_quality,
        'Secrets, SAST, Dependencies, and Workflow Security': args.static_security,
        'Functional and Integration Tests': args.functional_tests,
        'Frontend Reproducibility': args.frontend,
        'Production Image, Container Security, Runtime, and DAST': args.production_runtime,
    }
    if any(value != 'success' for value in gates.values()):
        raise SystemExit('Cannot publish Full Admission evidence unless every comprehensive gate succeeded.')
    payload = build_full_evidence(
        source_sha=args.source_sha,
        source_tree=args.source_tree,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        workflow_ref=args.workflow_ref,
        gates=gates,
    )
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


def _summary(args: argparse.Namespace) -> int:
    summary = render_operator_summary(
        result=args.result,
        profile=args.profile,
        commit_sha=args.commit_sha,
        tree_sha=args.tree_sha,
        evidence=args.evidence,
        fresh_checks=tuple(filter(None, (part.strip() for part in args.fresh_checks.split('|')))),
        reused_coverage=tuple(filter(None, (part.strip() for part in args.reused_checks.split('|')))),
        duration=args.duration,
        first_failure=args.first_failure,
        next_action=args.next_action,
        coverage_summary=args.coverage_summary,
    )
    if args.output:
        with Path(args.output).open('a', encoding='utf-8') as stream:
            stream.write(summary)
    else:
        print(summary, end='')
    return 0


def _test_summary(args: argparse.Namespace) -> int:
    print(render_test_taxonomy_summary(tuple(Path(path) for path in args.junit)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='KAORI progressive CI Admission policy helper')
    sub = parser.add_subparsers(dest='command', required=True)

    route = sub.add_parser('route')
    route.add_argument('--event-name', required=True)
    route.add_argument('--ref', required=True)
    route.add_argument('--base-ref', default='')
    route.add_argument('--head-ref', default='')
    route.add_argument('--changed-paths-file')
    route.set_defaults(func=_route)

    evidence = sub.add_parser('find-evidence')
    evidence.add_argument('--repository', required=True)
    evidence.add_argument('--token', required=True)
    evidence.add_argument('--workflow', default='quality.yml')
    evidence.add_argument('--start-sha', required=True)
    evidence.add_argument('--current-tree', required=True)
    evidence.set_defaults(func=_find_evidence)

    writer = sub.add_parser('write-evidence')
    writer.add_argument('--source-sha', required=True)
    writer.add_argument('--source-tree', required=True)
    writer.add_argument('--run-id', type=int, required=True)
    writer.add_argument('--run-attempt', type=int, required=True)
    writer.add_argument('--workflow-ref', required=True)
    writer.add_argument('--static-quality', required=True)
    writer.add_argument('--static-security', required=True)
    writer.add_argument('--functional-tests', required=True)
    writer.add_argument('--frontend', required=True)
    writer.add_argument('--production-runtime', required=True)
    writer.add_argument('--output', default='admission-evidence.json')
    writer.set_defaults(func=_write_evidence)

    summary = sub.add_parser('summary')
    summary.add_argument('--result', required=True)
    summary.add_argument('--profile', required=True)
    summary.add_argument('--commit-sha', required=True)
    summary.add_argument('--tree-sha', required=True)
    summary.add_argument('--evidence', required=True)
    summary.add_argument('--duration', required=True)
    summary.add_argument('--coverage-summary', default='')
    summary.add_argument('--fresh-checks', default='')
    summary.add_argument('--reused-checks', default='')
    summary.add_argument('--first-failure')
    summary.add_argument('--next-action', required=True)
    summary.add_argument('--output')
    summary.set_defaults(func=_summary)

    test_summary = sub.add_parser('test-summary')
    test_summary.add_argument('--junit', action='append', required=True)
    test_summary.set_defaults(func=_test_summary)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
