from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_settings_stays_two_workspace_navigation_without_redundant_overview() -> None:
    menu = read('app/templates/components/navigation/settings_menu.html')
    routes = read('app/settings/routes.py')
    readme = read('app/settings/README.md')

    assert 'General' in menu
    assert 'Account' in menu
    assert 'Settings Overview decision' in readme
    assert 'Settings does **not** have a dedicated Overview page' in readme
    assert "@bp.route('/', methods=['GET', 'POST'])" in routes
    assert not (ROOT / 'app/templates/settings/overview').exists()


def test_general_and_account_share_loading_and_action_feedback_contracts() -> None:
    general_actions = read('app/settings/general/actions.py')
    account_actions = read('app/settings/account/actions.py')
    general_page = read('app/templates/settings/general/partials/_page_content.html')
    general_tabs = read('app/templates/settings/general/partials/_tabs.html')
    timezone = read('app/templates/settings/general/partials/_time_locale.html')
    regional = read('app/templates/settings/general/partials/_regional_format.html')
    account_page = read('app/templates/settings/account/partials/_page_content.html')
    account_tabs = read('app/templates/settings/account/partials/_tabs.html')
    password = read('app/templates/settings/account/partials/_change_password.html')

    assert 'components/loading_bar.html' in general_page
    assert 'general-settings-loading' in general_page
    assert "hx_indicator='#general-settings-loading'" in general_tabs
    assert 'components/action_button.html' in timezone
    assert 'components/action_button.html' in regional

    assert 'components/loading_bar.html' in account_page
    assert 'account-settings-loading' in account_page
    assert "hx_indicator='#account-settings-loading'" in account_tabs
    assert 'hx-indicator="#account-settings-loading"' in password
    assert 'components/action_button.html' in password

    assert 'create_transient_feedback(' in general_actions
    assert 'create_transient_feedback(' in account_actions
    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in general_actions
    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in account_actions
    assert 'queue_feedback=not is_htmx' in general_actions
    assert 'queue_feedback=not is_htmx' in account_actions
    assert "reason_code='external_credential_owner'" in account_actions
