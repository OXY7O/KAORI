from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'access' / 'users' / 'partials' / '_content.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = 'surface_ui.block_classes()'


def test_user_directory_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert source.count(SHARED_SHELL) == 1
    assert COPIED_SHELL not in source

    # Preserve user-directory composition and HTMX behavior while moving only
    # the outer presentation-shell ownership to the shared primitive.
    markers = (
        'id="users-page-content"',
        'access/users/partials/_summary_cards.html',
        'id="user-directory"',
        'User Directory',
        'pagination.total_items',
        'registry_ui.clear_filters_action',
        "target='#users-page-content'",
        "indicator='#users-refresh-indicator'",
        "push_url='true'",
        "swap='outerHTML settle:150ms'",
        "sync='#users-filter-form:replace'",
        "loading_bar.render('users-refresh-indicator'",
        'access/users/partials/_filters.html',
        'id="users-table-content"',
        'access/users/partials/_table.html',
    )
    for marker in markers:
        assert marker in source


def test_user_directory_copied_shell_debt_is_removed() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
