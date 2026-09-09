from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'components' / '_status_notice.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border(?:/[0-9]+)?\b'
)


def test_status_notice_uses_shared_border_authority_with_legacy_warning_fallback() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert "{% import 'components/operational_callout.html' as operational_callout %}" in source
    assert "set border_tone = tone if tone in ['critical', 'info'] else 'warning'" in source
    assert 'operational_callout.semantic_border_classes(border_tone)' in source
    assert SEMANTIC_BORDER.findall(source) == []

    assert "set background_class = 'bg-status-critical-soft' if tone == 'critical'" in source
    assert "else ('bg-status-info-soft' if tone == 'info' else 'bg-status-warning-soft')" in source
    assert "set icon_class = 'text-status-critical' if tone == 'critical'" in source
    assert "else ('text-status-info' if tone == 'info' else 'text-status-warning')" in source
    assert 'role="status"' in source
    assert "macro render(title, message, tone='warning', icon='triangle-alert', extra_class='')" in source
    assert '{{ extra_class }}' in source


def test_status_notice_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
