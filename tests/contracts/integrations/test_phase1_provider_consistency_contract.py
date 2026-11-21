from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_phase1_adapters_reuse_named_sender_functions() -> None:
    registry = read('app/integrations/delivery/notification_channels/providers/__init__.py')
    for provider in ('ntfy', 'slack', 'discord'):
        assert f'def _send_{provider}(' in registry
        assert f'sender=_send_{provider},' in registry
        assert (
            f'sender=lambda credentials, destination, provider_config, message, timeout: send_{provider}_message'
            not in registry
        )
    for provider in ('telegram', 'email', 'microsoft_teams'):
        assert f"'{provider}': NotificationProviderAdapter(" in registry


def test_phase1_documentation_distinguishes_source_admission_from_provider_uat() -> None:
    doc = read('app/integrations/README.md')
    for token in (
        'Phase 1 adapter source is admitted in staging/main',
        'NOTIFICATION_NTFY_ALLOWED_ORIGINS',
        'NOTIFICATION_NTFY_CA_BUNDLE',
        'allowed_mentions: {"parse": []}',
        'source-level provider-specific `Retry-After` scheduling',
        'NotificationDelivery.next_retry_at',
        'Provider-specific UAT still pending',
        'NOTIFICATION_DELIVERY_RECOVERY_ENABLED=false',
    ):
        assert token in doc
    for obsolete in (
        'Phase 1 provider source merged to review',
        'Three new Phase 1 adapters are integrated to the review branch only',
        'does **not yet honor provider-specific',
    ):
        assert obsolete not in doc
