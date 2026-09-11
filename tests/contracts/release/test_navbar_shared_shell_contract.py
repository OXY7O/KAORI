from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'navbar.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card'
SHARED_SHELL = '{{ surface_ui.block_classes() }}'


def test_navbar_breadcrumb_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert f'class="{SHARED_SHELL} inline-flex h-10 min-w-0' in source
    assert COPIED_SHELL not in source

    assert 'x-data="kaoriNavbar"' in source
    assert '@keydown.escape.window="closeMenus()"' in source
    assert ':aria-expanded="sidebarExpanded.toString()"' in source
    assert 'aria-label="Breadcrumb"' in source
    assert '{% for item in breadcrumb_items %}' in source
    assert 'aria-current="page"' in source
    assert '{{ global_search.desktop_trigger() }}' in source
    assert '{{ global_search.mobile_trigger() }}' in source
    assert 'toggleQuickActions()' in source
    assert 'load_navigation_notification_context()' in source
    assert 'id="theme-toggle"' in source
    assert 'toggleUserMenu()' in source
    assert "url_for('auth.logout')" in source
    assert '{{ global_search.dialog() }}' in source


def test_navbar_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
