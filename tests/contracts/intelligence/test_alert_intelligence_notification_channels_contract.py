from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_intelligence_is_asset_scoped_multi_domain_and_keeps_source_authority_explicit():
    module = read('app/alert_intelligence/service.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')

    assert 'load_alerts_by_source' in module
    assert 'load_alert_stream' in module
    assert "_VALID_DOMAINS = {'kubernetes', 'object_storage'}" in module
    assert "_VALID_SOURCES = {'auto', 'alertmanager', 'prometheus'}" in module
    assert 'get_active_recommendation_findings' in module
    assert 'Alertmanager is preferred in Automatic mode' in workspace
    assert 'Prometheus ALERTS remains the fallback evidence path' in workspace
    assert 'contextual correlation, not a claim that every finding was caused by every alert' in correlation


def test_notification_channel_persistence_is_provider_neutral_and_secrets_are_encrypted():
    model = read('app/models/notification_channel.py')
    service = read('app/notification_channels/service.py')
    providers = read('app/notification_channels/providers/__init__.py')

    assert 'credential_payload: Mapped[str | None] = mapped_column(EncryptedText()' in model
    assert 'destination: Mapped[str | None]' in model
    assert 'provider_config: Mapped[dict[str, Any]]' in model
    assert 'bot_token: Mapped' not in model
    assert 'target_chat_id: Mapped' not in model
    assert 'get_notification_provider(channel.provider_key)' in service
    assert "'telegram': NotificationProviderAdapter(" in providers


def test_telegram_provider_uses_fixed_bot_api_and_template_never_echoes_token():
    provider = read('app/notification_channels/providers/telegram.py')
    page = read('app/templates/integrations/notification_channels/index.html')

    assert "_TELEGRAM_API = 'https://api.telegram.org'" in provider
    assert "f'{_TELEGRAM_API}/bot{bot_token}/sendMessage'" in provider
    assert "method='POST'" in provider
    assert "_TELEGRAM_TEXT_LIMIT = 4096" in provider
    assert "'link_preview_options'" in provider
    assert 'type="password"' in page
    assert 'form_channel.bot_token' not in page
    assert 'credential_configured' in page


def test_notification_dispatch_runs_on_existing_maintenance_queue_and_retries_failed_delivery():
    schedule = read('app/notification_channels/config.py')
    tasks = read('app/alert_delivery/tasks.py')
    service = read('app/notification_channels/service.py')

    assert "os.getenv('JOB_MAINTENANCE_CELERY_QUEUE') or 'maintenance'" in schedule
    assert "name='app.alert_delivery.tasks.dispatch_alert_intelligence_notifications'" in tasks
    assert "'retried': 0" in tasks
    assert 'notification_delivery_max_attempts()' in service
    assert "event_type='alert_intelligence.active_alert'" in service
    assert "delivery.status != 'failed' or delivery.attempt_count >= max_attempts" in service


def test_alert_intelligence_delivery_journal_is_scoped_to_selected_asset():
    alert_service = read('app/alert_intelligence/service.py')
    notification_service = read('app/notification_channels/service.py')

    assert "domain=domain" in alert_service
    assert "asset_key=selected_asset_key or None" in alert_service
    assert "domain: str | None = None" in notification_service
    assert "asset_key: str | None = None" in notification_service
    assert "NotificationDelivery.domain == domain" in notification_service
    assert "NotificationDelivery.asset_key == asset_key" in notification_service
