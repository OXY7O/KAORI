from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'components' / 'page_hero.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'

SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)


def test_page_hero_status_badge_uses_shared_semantic_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_label.html" as table_label %}' in source
    assert 'table_label.tone_border_classes(tone)' in source
    assert SEMANTIC_BORDER.findall(source) == []

    for surface_class in (
        'kaori-hero-status-normal',
        'kaori-hero-status-warning',
        'kaori-hero-status-critical',
        'kaori-hero-status-unknown',
        'kaori-hero-status-info',
    ):
        assert surface_class in source

    assert "else 'kaori-hero-status-info'" in source
    assert 'kaori-hero-status-badge' in source
    assert 'bg-white/95' in source


def test_page_hero_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
