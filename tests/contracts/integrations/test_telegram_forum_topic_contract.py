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
    assert "message_thread_id=topic_id" in registry
    assert 'name="telegram_topic_id"' in form
    assert "form_channel.telegram_topic_id" in form
    assert 'Test Delivery' in form


def test_channel_transport_change_and_recovery_snapshots_already_own_topic() -> None:
    service = read('app/integrations/delivery/notification_channels/service.py')
    assert 'or dict(data.provider_config) != dict(channel.provider_config or {})' in service
    assert 'provider_config = dict(data.provider_config)' in service
    assert "'provider_config': channel.provider_config" in service
    assert "if raw.get('channel') != current" in service
    assert "dict(channel.provider_config or {})" in service
    assert "def test_channel(" in service


def test_github_actions_topic_stays_separate_from_application_events() -> None:
    workflow = read('.github/workflows/telegram-github-actions.yml')
    notifier = read('scripts/ci_delivery_notify.py')
    catalog = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID' in workflow
    assert "'message_thread_id': topic_id" in notifier
    assert 'github_actions.' not in catalog
