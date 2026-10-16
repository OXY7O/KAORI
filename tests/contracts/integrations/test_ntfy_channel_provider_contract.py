from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_ntfy_uses_existing_provider_adapter_and_governed_delivery() -> None:
    registry = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    adapter = read('app/integrations/delivery/notification_channels/providers/ntfy.py')
    form = read('app/templates/integrations/delivery/notification_channels/providers/ntfy/_form.html')
    assert "'ntfy': NotificationProviderAdapter(" in registry
    assert 'send_ntfy_message' in registry
    assert 'NOTIFICATION_NTFY_ALLOWED_ORIGINS' in adapter
    assert 'ssl.create_default_context(cafile=ca_path or None)' in adapter
    assert 'ProxyHandler({})' in adapter and 'DenyRedirects()' in adapter
    assert 'name="ntfy_access_token"' in form
    assert 'form_channel.ntfy_access_token' not in form


def test_ntfy_inherits_channel_validation_and_recovery_policy() -> None:
    svc = read('app/integrations/delivery/notification_channels/service.py')
    assert 'or dict(data.provider_config) != dict(channel.provider_config or {})' in svc
    assert "'provider_config': channel.provider_config" in svc
    assert "if raw.get('channel') != current" in svc
    assert 'def test_channel(' in svc
    assert 'NOTIFICATION_DELIVERY_RECOVERY_ENABLED' in read('app/integrations/delivery/notification_channels/config.py')
