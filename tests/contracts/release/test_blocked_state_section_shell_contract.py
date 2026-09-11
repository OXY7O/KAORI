from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'components' / 'states' / '_blocked_state.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = '{{ table_ui.block_classes() }}'


def test_blocked_state_default_section_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as table_ui %}' in source
    assert SHARED_SHELL in source
    assert COPIED_SHELL not in source

    assert "blocked_state_variant|default('section')" in source
    assert "state_variant == 'posture'" in source
    assert "state_variant == 'table'" in source
    assert 'data-kaori-blocked-state' in source
    assert 'blocked_state_permission_granted|default(none)' in source
    assert 'state_show_admin_required' in source
    assert 'blocked_state_steps' in source
    assert 'Admin Required' in source


def test_blocked_state_default_section_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
