import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_owned_optional_topic_config_is_sent_via_bot_api() -> None:
    telegram = read('app/integrations/delivery/notification_channels/providers/telegram.py')
    registry = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    form = read('app/templates/integrations/delivery/notification_channels/providers/telegram/_form.html')
    assert "form.get('telegram_topic_id')" in telegram
    assert "'message_thread_id': topic_id if topic_id is not None else raw_topic_id" in telegram
    assert "payload['message_thread_id'] = message_thread_id" in telegram
    assert "raw_topic_id = provider_config.get('message_thread_id')" in registry
    assert 'message_thread_id=topic_id' in registry
    assert 'name="telegram_topic_id"' in form
    assert 'form_channel.telegram_topic_id' in form
    catalog = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    assert 'Changing this requires a new Test Delivery.' in catalog


def test_channel_transport_change_and_recovery_snapshots_already_own_topic() -> None:
    service = read('app/integrations/delivery/notification_channels/service.py')
    assert 'or dict(data.provider_config) != dict(channel.provider_config or {})' in service
    assert 'provider_config = dict(data.provider_config)' in service
    assert "'provider_config': channel.provider_config" in service
    assert "if raw.get('channel') != current" in service
    assert 'dict(channel.provider_config or {})' in service
    assert 'def test_channel(' in service


def test_github_actions_topic_stays_separate_from_application_events() -> None:
    workflow = read('.github/workflows/telegram-github-actions.yml')
    notifier = read('scripts/ci_delivery_notify.py')
    catalog = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID' in workflow
    assert "'message_thread_id': topic_id" in notifier
    assert 'github_actions.' not in catalog


def test_telegram_uses_section_title_guide_and_one_desktop_input_row() -> None:
    form = read('app/templates/integrations/delivery/notification_channels/providers/telegram/_form.html')
    modal = read('app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html')
    info_tip = read('app/templates/components/info_tip.html')
    javascript = read('app/static/js/info_tips.js')

    assert 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3' in form
    assert 'sm:col-span-2' not in form
    assert '<p class=' not in form
    assert 'info_tip.render(' not in form
    assert '{% import "components/info_tip.html" as info_tip %}' in modal
    registry = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    assert "'telegram': NotificationProviderAdapter(" in registry
    assert "'notification-' ~ provider_option.key ~ '-configuration-guide'" in modal
    assert "variant='guide'" in modal
    assert 'flex flex-wrap items-center gap-2' in modal

    for field, field_id in (
        ('bot_token', 'notification-telegram-token'),
        ('target_chat_id', 'notification-telegram-chat-id'),
        ('telegram_topic_id', 'telegram-topic-id'),
    ):
        assert f'name="{field}"' in form
        assert f'for="{field_id}"' in form
        assert f'id="{field_id}"' in form
    assert 'type="password"' in form
    assert 'autocomplete="new-password"' in form
    assert 'inputmode="numeric"' in form
    assert 'pattern="[0-9]*"' in form
    assert 'form_channel.telegram_topic_id' in form

    for guidance in (
        'Bot Token: Stored as a secret and never rendered back after save.',
        'Chat ID / @Channel: The bot must already be able to post to this destination.',
        'Numeric Telegram message_thread_id of a Forum Topic in your supergroup.',
        'Leave blank for ordinary chat delivery.',
        'Changing this requires a new Test Delivery.',
    ):
        assert guidance in registry
    assert "data-kaori-info-tip-variant=\"{{ 'guide' if guide_variant else 'action' if action_variant else 'icon' }}\"" in info_tip
    assert 'role="tooltip"' in info_tip
    assert "root.closest('dialog[open]')" in javascript
    assert 'openDialog instanceof HTMLDialogElement ? openDialog : document.body' in javascript
    assert 'portal.appendChild(preview)' in javascript
    assert "addEventListener('focusin'" in javascript
    assert "addEventListener('keydown'" in javascript
    assert re.search(r"window\.addEventListener\(\s*['\"]scroll['\"]", javascript) is not None
