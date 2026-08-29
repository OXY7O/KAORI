from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
WELCOME_VERIFIER = ROOT / 'scripts/verify_welcome_final_lock.py'


def run_verifier(relative: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / relative)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def load_welcome_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location('kaori_verify_welcome_final_lock', WELCOME_VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_governance_keeps_concise_human_header() -> None:
    result = run_verifier('scripts/verify_release_governance.py')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'PASS — KAORI Release Governance'


def test_welcome_final_lock_uses_sectioned_human_readable_success_output() -> None:
    result = run_verifier('scripts/verify_welcome_final_lock.py')
    assert result.returncode == 0, result.stdout + result.stderr

    output = result.stdout
    assert output.splitlines()[0] == 'PASS — KAORI Welcome Final Lock'
    for section in (
        'Routing & Access — PASS',
        'Role-Aware Discoverability — PASS',
        'KAORI UI Standard — PASS',
        'Release Evidence — PASS',
    ):
        assert section in output

    assert 'Summary — 4 passed · 0 failed' in output
    assert 'final-lock v3 passed:' not in output


def test_welcome_final_lock_failure_is_sectioned_actionable_and_keeps_exit_semantics(
    monkeypatch,
    capsys,
) -> None:
    verifier = load_welcome_verifier()

    def fail_routing(errors: list[str]) -> None:
        errors.append('Welcome index route is missing.')

    monkeypatch.setattr(verifier, '_verify_route_contract', fail_routing)
    monkeypatch.setattr(verifier, '_verify_catalog_contract', lambda errors: None)
    monkeypatch.setattr(verifier, '_verify_presentation_contract', lambda errors: None)
    monkeypatch.setattr(verifier, '_verify_release_evidence', lambda errors: None)

    assert verifier.main() == 1
    output = capsys.readouterr().out

    assert output.splitlines()[0] == 'FAIL — KAORI Welcome Final Lock'
    assert 'Routing & Access — FAIL' in output
    assert 'Role-Aware Discoverability — PASS' in output
    assert 'KAORI UI Standard — PASS' in output
    assert 'Release Evidence — PASS' in output
    assert 'WHAT — Welcome index route is missing.' in output
    assert 'WHY —' in output
    assert 'WHERE —' in output
    assert 'Summary — 3 passed · 1 failed' in output
    assert 'ERROR:' not in output
