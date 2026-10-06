from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'materialization' / '_pending.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border(?:/[0-9]+)?\b'
)


def test_materialization_error_uses_shared_critical_border_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/operational_callout.html" as operational_callout %}' in source
    assert "set critical_border_class = operational_callout.semantic_border_classes('critical')" in source
    assert source.count('{{ critical_border_class }}') == 2
    assert 'border {{ critical_border_class }} bg-status-critical-soft p-4' in source
    assert 'border-t {{ critical_border_class }} pt-3' in source
    assert SEMANTIC_BORDER.findall(source) == []

    assert 'hx-trigger="every 5s"' in source
    assert "table_label.status_label('Failed' if preparation_error else 'Preparing'," in source
    assert "'critical' if preparation_error else 'pending')" in source
    assert 'bg-status-critical-soft' in source
    assert 'text-status-critical-text' in source
    assert 'role="progressbar"' in source
    assert '>Job Log<' not in source
    assert 'Job Log' in source
    assert 'Retry' in source


def test_materialization_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
