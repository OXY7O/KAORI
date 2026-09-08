from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'components' / 'operational_toast.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'

SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)


def test_operational_toast_uses_shared_semantic_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert "{% import 'components/table_label.html' as table_label %}" in source
    assert "table_label.tone_border_classes('normal')" in source
    assert "table_label.tone_border_classes('critical')" in source
    assert SEMANTIC_BORDER.findall(source) == []

    assert 'bg-status-normal-soft px-2.5 py-2' in source
    assert 'bg-status-critical-soft px-2.5 py-2' in source
    assert 'text-status-normal-text' in source
    assert 'text-status-critical-text' in source


def test_operational_toast_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
