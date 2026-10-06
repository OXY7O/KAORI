from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'access' / 'roles' / 'partials' / '_role_detail.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)


def test_access_role_detail_uses_shared_semantic_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_label.html" as table_label %}' in source
    assert "table_label.tone_border_classes('warning')" in source
    assert "table_label.tone_border_classes('critical')" in source
    assert SEMANTIC_BORDER.findall(source) == []
    assert 'Remove {{ detail.assigned_users }} user assignment' in source
    assert 'data-destructive-modal-id="role-delete-confirmation"' in source
    assert 'hover:bg-status-critical hover:text-white' in source


def test_access_role_detail_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
