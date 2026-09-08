from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'components' / 'states' / '_flash_messages.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'

RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)


def test_global_flash_messages_use_semantic_status_tones() -> None:
    source = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert "{% import 'components/table_label.html' as table_label %}" in source
    assert 'table_label.tone_surface_classes(resolved_tone)' in source
    assert 'table_label.tone_border_classes(resolved_tone)' in source
    assert RAW_PALETTE.findall(source) == []


def test_global_flash_message_style_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
