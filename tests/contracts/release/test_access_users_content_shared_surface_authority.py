from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'access' / 'users' / 'partials' / '_content.html'
DIRECTORY_PATH = ROOT / 'app' / 'templates' / 'access' / 'users' / 'partials' / '_directory.html'
FILTERS_PATH = ROOT / 'app' / 'templates' / 'access' / 'users' / 'partials' / '_filters.html'
REGISTRY_PATH = ROOT / 'app' / 'templates' / 'components' / 'table_registry.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = 'surface_ui.block_classes()'


def test_user_directory_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')
    directory = DIRECTORY_PATH.read_text(encoding='utf-8')
    filters = FILTERS_PATH.read_text(encoding='utf-8')
    registry = REGISTRY_PATH.read_text(encoding='utf-8')

    # The approved page composes the registry from its owned child partial.
    assert 'id="users-page-content"' in source
    assert 'access/users/partials/_summary_cards.html' in source
    assert 'access/users/partials/_directory.html' in source
    assert '{% import "components/table_primitives.html" as surface_ui %}' in directory
    assert directory.count(SHARED_SHELL) == 1
    assert COPIED_SHELL not in source
    assert COPIED_SHELL not in directory

    for marker in (
        'id="user-directory"',
        'User Directory',
        'pagination.total_items',
        "registry_ui.clear_filters_link('users.index'",
        "loading_bar.render('users-refresh-indicator'",
        'access/users/partials/_filters.html',
        'id="users-table-content"',
        'access/users/partials/_table.html',
    ):
        assert marker in directory

    assert 'registry_ui.filter_form(' in filters
    assert "'users.index'" in filters
    assert "'user-directory'" in filters
    assert "'users-refresh-indicator'" in filters
    assert "form_id='users-filter-form'" in filters
    assert 'aria_label=\'User Directory filters\'' in filters

    # Canonical HTMX semantics are owned by a shared registry macro, not by
    # obsolete page-local attribute copies. The swap targets the registry.
    for marker in (
        'hx-get="{{ url_for(endpoint) }}"',
        'hx-target="#{{ registry_id }}"',
        'hx-select="#{{ registry_id }}"',
        'hx-swap="outerHTML"',
        'hx-push-url="true"',
        'hx-indicator="#{{ loading_id }}"',
        'hx-sync="closest section:replace"',
        'data-kaori-canonical-registry-filter="{{ registry_id }}"',
    ):
        assert marker in registry


def test_user_directory_copied_shell_debt_is_removed() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
