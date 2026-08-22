from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_operations_reuses_integrations_notification_channels_without_credentials() -> None:
    routing = read('app/intelligence/alert_intelligence/routing.py')
    model = read('app/models/notification_channel.py')
    workspace = read('app/templates/intelligence/partials/_alert_ops_routing.html')

    assert 'NotificationChannel' in routing
    assert 'credential_payload' not in routing
    assert 'credential_payload: Mapped[str | None] = mapped_column(EncryptedText()' in model
    assert 'Integrations → Notification Channels' in workspace
    assert "url_for('notification_channels.index')" in workspace


def test_alert_operations_has_provider_specific_firing_and_resolved_templates() -> None:
    module = read('app/intelligence/alert_intelligence/templates.py')
    workspace = read('app/templates/intelligence/partials/_alert_ops_templates.html')

    for provider in ('telegram', 'email', 'microsoft_teams'):
        assert f"'{provider}'" in module
    assert module.count("'firing'") >= 3
    assert module.count("'resolved'") >= 3
    for variable in ('resolution_summary', 'verification_evidence', 'operator_name', 'case_id'):
        assert variable in module
    assert 'Built-in' in workspace
    assert 'Override' in workspace


def test_firing_and_resolved_delivery_use_existing_delivery_ledger() -> None:
    notifications = read('app/intelligence/alert_intelligence/notifications.py')
    event_catalog = read('app/definitions/catalogs/platform_operations/notifications/outbound_delivery.yaml')
    channel_service = read('app/integrations/delivery/notification_channels/service.py')

    assert 'dispatch_notification_event' in notifications
    assert 'NotificationDelivery' in notifications
    assert "event_type = 'alert_ops.resolved' if event_state == 'resolved' else 'alert_ops.firing'" in notifications
    assert 'alert_ops.firing:' in event_catalog
    assert 'alert_ops.resolved:' in event_catalog
    assert "event_type in {'alert_ops.firing', 'alert_ops.resolved'}" in channel_service


def test_resolved_delivery_targets_only_channels_that_received_firing() -> None:
    notifications = read('app/intelligence/alert_intelligence/notifications.py')

    assert '_successful_firing_channel_ids(case)' in notifications
    assert "NotificationDelivery.event_type == 'alert_ops.firing'" in notifications
    assert "NotificationDelivery.status == 'sent'" in notifications
    assert 'policy_allows_resolved(case, channel_id)' in notifications
    assert "case.source_state == 'resolved' and case.workflow_state == 'closed'" in notifications
