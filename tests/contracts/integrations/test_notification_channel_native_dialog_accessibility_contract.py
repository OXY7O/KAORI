import re
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


def test_configuration_modal_scrollable_cards_keep_spaced_fixed_actions() -> None:
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    buttons = read('app/templates/components/action_button.html')

    assert 'overflow-y-auto overscroll-contain bg-surface-page' in modal
    assert 'space-y-5 p-4 sm:p-6' in modal
    assert 'Channel Details' in modal
    assert 'Delivery Policy' in modal
    assert '{% include provider_option.form_partial %}' in modal
    assert 'rounded-xl border border-outline-default bg-surface-card p-5 shadow-sm sm:p-6' in modal
    assert 'sm:grid-cols-2 xl:grid-cols-3' in modal
    assert 'aria-label="Notification Channel Actions"' in modal
    assert 'sm:px-7 sm:py-5' in modal
    assert 'justify-end gap-3' in modal
    assert "action_button.classes('secondary')" in modal
    assert "action_button.classes('primary')" in modal
    assert 'inline-flex h-10' in buttons
    for name in ('csrf_token', 'provider_key', 'name', 'minimum_severity', 'domains', 'event_types', 'enabled'):
        assert f'name="{name}"' in modal
    assert 'form_channel.provider_key' in modal
    assert 'data-kaori-dialog-transition' in modal


def test_notification_channel_configuration_fields_have_associated_labels() -> None:
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')

    for field_id, name, label in (
        ('notification-channel-name', 'name', 'Channel Name'),
        ('notification-channel-provider', 'provider_key', 'Provider'),
        ('notification-channel-minimum-severity', 'minimum_severity', 'Minimum Alert Severity'),
    ):
        assert modal.count(f'id="{field_id}"') == 1
        assert re.search(
            rf'<label for="{field_id}"[^>]*>{label}</label>\s*'
            rf'<(?:input|select) id="{field_id}"\s+name="{name}"',
            modal,
        )

    # Edit mode is immutable metadata, never a label pointing at a missing select.
    assert re.search(
        r'{% if form_channel %}\s*<dl>\s*<dt[^>]*>Provider</dt>\s*'
        r'<dd[^>]*>',
        modal,
    )
    assert 'name="provider_key"' in modal  # Hidden edit value and create select stay intact.
    assert 'name="csrf_token"' in modal
    assert '{% include provider_option.form_partial %}' in modal
    assert modal.count('data-kaori-native-dialog') == 2
