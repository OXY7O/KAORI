"""Offline failure-matrix regression for the read-only ruleset inventory (#4216)."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/audit_branch_rulesets.sh"


def test_partial_effective_ruleset_failure_preserves_other_inventory(tmp_path: Path) -> None:
    """A single failed branch lookup must not falsely attest complete coverage."""
    calls = tmp_path / "calls.txt"
    mock = tmp_path / "gh"
    mock.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$AUDIT_CALLS"\n'
        'if [[ "$*" == "ruleset check main --repo OXY7O/KAORI" ]]; then exit 1; fi\n'
        "exit 0\n",
        encoding="utf-8",
    )
    mock.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env["AUDIT_CALLS"] = str(calls)
    result = subprocess.run(
        ["bash", str(SCRIPT), "OXY7O/KAORI", "OXY7O/kaori-docs"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    observed = calls.read_text(encoding="utf-8").splitlines()
    assert result.returncode == 1
    assert "INCOMPLETE" in result.stderr
    assert "INVENTORY COMPLETE" not in result.stdout
    assert len(observed) == 6
    assert "ruleset check kaori/staging --repo OXY7O/KAORI" in observed
    assert "ruleset check main --repo OXY7O/kaori-docs" in observed
    assert "ruleset check kaori/staging --repo OXY7O/kaori-docs" in observed
