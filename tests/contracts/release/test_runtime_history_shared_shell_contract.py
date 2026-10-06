from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'integrations' / 'partials' / '_runtime_history.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = '{{ surface_ui.block_classes() }}'


def test_runtime_history_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert f'class="relative {SHARED_SHELL}"' in source
    assert COPIED_SHELL not in source

    assert '<section id="{{ runtime_history_id }}"' in source
    assert '{% if runtime_history_oob|default(false) %}hx-swap-oob="outerHTML"{% endif %}' in source
    assert 'data-kaori-runtime-history-standard-v2' in source
    assert 'data-kaori-runtime-history-actions' in source
    assert 'data-kaori-runtime-history-filters' in source
    assert 'data-kaori-runtime-history-table' in source
    assert 'data-kaori-runtime-observation-modals' in source
    assert '{{ pagination_ui.footer_classes() }}' in source
    assert "{% include 'components/states/_empty_state.html' %}" in source


def test_runtime_history_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
