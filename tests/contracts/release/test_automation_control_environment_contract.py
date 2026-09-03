from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_automation_control_verifier_uses_split_production_app_contract() -> None:
    verifier = read('scripts/verify_automation_control.py')
    production_app = read('deploy/env/app.env.example')

    assert "env_production = read('deploy/env/app.env.example')" in verifier
    assert "env_production = read('.env.production.example')" not in verifier
    assert 'AUTOMATION_EXECUTION_ENABLED=false' in production_app
    assert 'CUSTOM_RUNBOOK_AUTHORING_ENABLED=false' in production_app
