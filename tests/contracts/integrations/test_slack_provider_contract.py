from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_slack_adapter_reuses_existing_delivery_contract_and_secret_boundary() -> None:
    catalog = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    provider = read('app/integrations/delivery/notification_channels/providers/slack.py')
    template = read('app/templates/integrations/delivery/notification_channels/providers/slack/_form.html')
    assert "'slack': NotificationProviderAdapter(" in catalog
    assert 'send_slack_message(' in catalog
    assert "'webhook_url': webhook_url or old.get('webhook_url', '')" in provider
    assert "('webhook_url')" not in template
    assert 'form_channel.slack_webhook_url' not in template
    assert "name=\"slack_webhook_url\"" in template
    assert 'DenyRedirects()' in provider and 'ProxyHandler({})' in provider


def test_slack_event_policy_and_replay_remain_source_owned() -> None:
    source = read('app/integrations/delivery/notification_channels/service.py')
    assert "or dict(data.provider_config) != dict(channel.provider_config or {})" in source
    assert "'credential_payload': channel.credential_payload" in source
    assert "if raw.get('channel') != current" in source
    assert "def test_channel(" in source
