from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'access' / 'permissions' / 'index.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'

WARNING_BORDER = re.compile(r'\bborder-status-warning-border\b')


def test_permission_catalog_registry_drift_uses_shared_warning_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert "table_label.tone_border_classes('warning')" in source
    assert WARNING_BORDER.findall(source) == []
    assert 'bg-status-warning-soft' in source
    assert 'text-status-warning-text' in source
    assert 'Registry Drift Detected' in source
    assert 'triangle-alert' in source
    assert '{% if summary.drift_count %}' in source


def test_permission_catalog_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
