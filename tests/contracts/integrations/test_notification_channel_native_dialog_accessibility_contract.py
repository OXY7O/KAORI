from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(p: str) -> str:
    return (ROOT / p).read_text(encoding='utf-8')


def test_notification_channels_use_native_modal_focus_contract() -> None:
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    controls = read('app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html')
    assert modal.count('<dialog id="notification-channel-') == 2
    assert modal.count('data-kaori-native-dialog') == 2
    assert modal.count('autofocus') == 2
    assert 'data-kaori-dialog-auto-open' in modal
    assert modal.count('data-kaori-dialog-transition') == 2
    assert 'x-show="guideOpen"' not in modal
    assert 'x-show="configOpen"' not in modal
    assert 'data-dialog-target="notification-channel-guide-dialog"' in controls
    assert 'data-dialog-target="notification-channel-config-dialog"' in controls
    assert 'data-kaori-dialog-open' in controls
    assert 'configOpen' not in controls
    assert 'guideOpen' not in controls


def test_shared_native_dialog_handler_supports_safe_cross_dialog_transition() -> None:
    javascript = read('app/static/js/native_dialogs.js')
    assert "opener.matches('[data-kaori-dialog-transition]')" in javascript
    assert 'current.close()' in javascript
    assert 'openDialog(opener)' in javascript
    assert "typeof dialog.showModal === 'function'" in javascript
    assert 'dialog.close()' in javascript
    assert 'data-kaori-dialog-auto-open' in javascript
    assert 'autofocus' in javascript


def test_credentials_and_csrf_remain_inside_the_native_configuration_form() -> None:
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    assert 'method="post"' in modal
    assert 'name="csrf_token"' in modal
    assert 'name="provider_key"' in modal
    assert 'role="dialog"' not in modal
    assert 'data-kaori-dialog-close' in modal
