from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
TARGETS = (
    ROOT / 'app' / 'templates' / 'access' / 'roles' / 'form.html',
    ROOT / 'app' / 'templates' / 'access' / 'roles' / 'partials' / '_role_detail.html',
)
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)


def test_access_role_surfaces_use_shared_semantic_border_authority() -> None:
    for template_path in TARGETS:
        source = template_path.read_text(encoding='utf-8')
        assert '{% import "components/table_label.html" as table_label %}' in source
        assert 'table_label.tone_border_classes(' in source
        assert SEMANTIC_BORDER.findall(source) == []


def test_access_role_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))

    for template_path in TARGETS:
        relative = template_path.relative_to(ROOT).as_posix()
        assert relative not in payload['files']
