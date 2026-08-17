from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_settings_navigation_keeps_current_ownership_boundary() -> None:
    menu = _read('app/templates/components/navigation/settings_menu.html')
    assert 'settings.general' in menu
    assert 'settings.account' in menu
    assert 'users.index' not in menu
    assert 'access.roles' not in menu
    assert 'access.activity_audit.index' not in menu


def test_account_tabs_follow_general_settings_tab_contract() -> None:
    general_tabs = _read('app/templates/settings/general/partials/_tabs.html')
    account_tabs = _read('app/templates/settings/account/partials/_tabs.html')

    for token in (
        'border-b border-outline-default bg-surface-subtle px-5 pt-4',
        'flex gap-2 overflow-x-auto',
        'min-h-10 shrink-0',
        'border-b-surface-card',
        'hover:bg-kaori-soft hover:text-kaori-primary',
    ):
        assert token in general_tabs
        assert token in account_tabs


def test_recent_authentication_activity_uses_shared_table_and_status_primitives() -> None:
    activity = _read('app/templates/settings/account/partials/_recent_login_activity.html')
    assert 'components/table.html' in activity
    assert 'components/table_label.html' in activity
    assert 'table_ui.table_classes' in activity
    assert 'table_ui.header_cell_classes' in activity
    assert 'table_ui.row_classes' in activity
    assert "table_label.status_indicator_label('Success', 'normal')" in activity
    assert "table_label.status_indicator_label('Failed', 'critical')" in activity
    assert 'border-status-normal-border' not in activity
    assert 'border-status-critical-border' not in activity


def test_general_settings_retired_side_context_is_not_reintroduced() -> None:
    page = _read('app/templates/settings/general/partials/_page_content.html')
    assert not (ROOT / 'app/templates/settings/general/partials/_impact_information.html').exists()
    assert '_impact_information.html' not in page
    assert 'data-timezone-preference-boundary="inline"' in _read(
        'app/templates/settings/general/partials/_time_locale.html'
    )
    assert 'data-regional-preference-boundary="inline"' in _read(
        'app/templates/settings/general/partials/_regional_format.html'
    )


def test_general_settings_feedback_contract_matches_audit_only_delivery() -> None:
    readme = _read('app/settings/README.md')
    routes = _read('app/settings/routes.py')
    assert 'shared KAORI operational result toast' in readme
    assert 'do not create unread Notification Center items' in readme
    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in routes
