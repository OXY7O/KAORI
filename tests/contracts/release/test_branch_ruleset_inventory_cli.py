"""Executable, offline regression tests for the read-only ruleset inventory (#4216)."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/audit_branch_rulesets.sh"


def _run(tmp_path: Path, arguments: list[str], *, fail: bool = False) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    binary = tmp_path / "gh"
    calls = tmp_path / "calls.txt"
    binary.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$AUDIT_CALLS"\n'
        + ('exit 1\n' if fail else 'exit 0\n'),
        encoding="utf-8",
    )
    binary.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env["AUDIT_CALLS"] = str(calls)
    result = subprocess.run(
        ["bash", str(SCRIPT), *arguments],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    return result, calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []


def test_default_inventory_uses_only_read_only_ruleset_queries(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, [])
    assert result.returncode == 0, result.stderr
    assert len(calls) == 9
    for repo in ("OXY7O/KAORI", "OXY7O/kaori-website", "OXY7O/kaori-docs"):
        assert f"ruleset list --repo {repo}" in calls
        assert f"ruleset check main --repo {repo}" in calls
        assert f"ruleset check kaori/staging --repo {repo}" in calls
    assert all(call.startswith(("ruleset list ", "ruleset check ")) for call in calls)
    assert "manual legacy protection" in result.stdout


def test_invalid_argument_rejected_before_any_authenticated_lookup(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, ["OXY7O/KAORI", "../invalid"])
    assert result.returncode == 2
    assert "invalid owner/repository" in result.stderr
    assert calls == []


def test_lookup_failure_is_fail_closed_not_reported_as_complete(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, ["OXY7O/KAORI"], fail=True)
    assert result.returncode == 1
    assert len(calls) == 1
    assert "INCOMPLETE" in result.stderr
    assert "INVENTORY COMPLETE" not in result.stdout
