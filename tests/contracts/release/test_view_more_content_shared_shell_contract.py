from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'components' / 'view_more_content.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = '{{ table_ui.block_classes() }}'


def test_view_more_content_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as table_ui %}' in source
    assert SHARED_SHELL in source
    assert COPIED_SHELL not in source

    assert 'class="group ' in source
    assert '{{ extra_classes }}' in source
    assert 'aria-label="{{ aria_label or title }}"' in source
    assert '{% if open_by_default %}open{% endif %}' in source
    assert '<summary class="list-none cursor-pointer select-none border-b border-outline-subtle' in source
    assert '{% if not compact_action %}' in source
    assert '{{ closed_label }}' in source
    assert '{{ open_label }}' in source
    assert 'data-lucide="chevron-down"' in source
    assert '{{ caller() }}' in source


def test_view_more_content_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
