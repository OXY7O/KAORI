from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_discord_adapter_reuses_shared_governance_and_disallows_mentions() -> None:
    catalog = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    provider = read('app/integrations/delivery/notification_channels/providers/discord.py')
    form = read('app/templates/integrations/delivery/notification_channels/providers/discord/_form.html')
    assert "'discord': NotificationProviderAdapter(" in catalog
    assert "'allowed_mentions': {'parse': []}" in provider
    assert "'discord.com'" in provider
    assert 'DenyRedirects()' in provider and 'ProxyHandler({})' in provider
    assert "name=\"discord_webhook_url\"" in form
    assert 'form_channel.discord_webhook_url' not in form
    assert "def parse_form(" in provider and "def form_view(" in provider


def test_discord_inherits_delivery_idempotency_and_retry_guard() -> None:
    service = read('app/integrations/delivery/notification_channels/service.py')
    assert "or dict(data.provider_config) != dict(channel.provider_config or {})" in service
    assert "'credential_payload': channel.credential_payload" in service
    assert 'def recover_notification_deliveries' in service
    assert "if raw.get('channel') != current" in service
    assert "def test_channel(" in service
