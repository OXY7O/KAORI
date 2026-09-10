from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'


def test_auth_setup_warning_border_uses_shared_semantic_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/operational_callout.html" as operational_callout %}' in source
    assert "operational_callout.semantic_border_classes('warning')" in source
    assert 'border-status-warning-border' not in source


def test_auth_setup_warning_border_debt_is_burned_down_only() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()
    metrics = payload['files'][relative]

    assert metrics.get('semantic_border_utilities', 0) == 0
    assert metrics.get('custom_hero_titles') == 1
