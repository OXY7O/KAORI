"""Source-level admission boundary for the Notification Delivery archive-only workstream.

Executable integration, SQL snapshot, archive checksums and negative cleanup
remain DevContainer UAT gates and must not be inferred from these contracts.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_domain_registered_and_uses_canonical_archive_engine() -> None:
    adapter = read('app/platform_operations/data_lifecycle/retention/domains/notification_delivery.py')
    registry = read('app/platform_operations/data_lifecycle/retention/domains/__init__.py')
    assert "name = 'notification_delivery'" in adapter
    assert "source_model = 'notification_deliveries'" in adapter
    assert 'cleanup_supported = False' in adapter
    assert "'notification_delivery': NotificationDeliveryArchiveDomain" in registry
    assert 'def inspect_boundary(' in adapter
    assert 'def iter_records(' in adapter
    assert 'def cleanup_records(' in adapter
    assert "return resolve_policy(" in adapter
    assert 'enabled=False' in adapter
    assert 'retention_days=90' in adapter
    assert 'archive_retention_days=365' in adapter


def test_archive_eligibility_is_terminal_and_non_destructive() -> None:
    adapter = read('app/platform_operations/data_lifecycle/retention/domains/notification_delivery.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    assert "NotificationDelivery.status.in_(('sent', 'skipped'))" in adapter
    assert 'NotificationDelivery.created_at < cutoff_at' in adapter
    assert 'NotificationDelivery.updated_at < cutoff_at' in adapter
    assert 'NotificationDelivery.id <= boundary.maximum_record_id' in adapter
    assert '.limit(policy.batch_size)' in adapter
    assert 'raise RuntimeError(' in adapter.split('def cleanup_records(', 1)[1]
    assert "if cleanup and not getattr(domain, 'cleanup_supported', True)" in engine
    assert engine.index("if cleanup and not getattr(domain, 'cleanup_supported', True)") < engine.index(
        'with retention_lock(domain.name):'
    )


def test_archive_exports_correlation_but_never_payload_or_replay_envelope() -> None:
    adapter = read('app/platform_operations/data_lifecycle/retention/domains/notification_delivery.py')
    serialization = adapter.split('def iter_records(', 1)[1].split('def cleanup_records(', 1)[0]
    assert "'event_key': row.event_key" in serialization
    assert "'channel_id': row.channel_id" in serialization
    assert "'status': row.status" in serialization
    assert "'attempt_count': row.attempt_count" in serialization
    assert 'row.payload_json' not in serialization
    assert 'row.credential_payload' not in serialization
    assert 'row.error_message' not in serialization
    assert '_encrypted_transport_snapshot' not in serialization


def test_policy_queue_schedule_and_ui_refuse_unadmitted_cleanup() -> None:
    admission = read('app/platform_operations/data_lifecycle/service.py')
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    ui = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    assert "not getattr(domain, 'cleanup_supported', True)" in admission
    assert "'cleanup_not_admitted'" in admission
    assert "domain_name not in {'notification_delivery', 'audit_event'}" in admission
    assert "if domain_name in {'notification_delivery', 'audit_event'}:" in presentation
    assert "selected.name not in ('notification_delivery', 'audit_event')" in ui
    assert 'Manual archive-only' in ui
    assert '<span class="font-semibold text-kaori-primary dark:text-kaori-accent">Archive Only</span>' in ui
    assert "data_lifecycle.run" in ui
    assert 'name="mode" value="archive_only"' in ui


def test_owner_and_coverage_are_truthful() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    assert "'notification_delivery': 'Notification Delivery'" in presentation
    assert "'notification_delivery': 'send'" in presentation
    assert 'Hot records retain deduplication, channel dependencies and lifetime counts' in presentation
    assert 'per-record archive search' in presentation


def test_notification_identity_schema_stays_inert_until_rollout_is_admitted() -> None:
    model = read('app/models/notification_channel.py')
    migration = read('migrations/versions/20261023_notification_delivery_identity.py')
    service = read('app/integrations/delivery/notification_channels/service.py')
    adapter = read('app/platform_operations/data_lifecycle/retention/domains/notification_delivery.py')
    assert 'class NotificationDeliveryIdentity(db.Model):' in model
    assert "UniqueConstraint('channel_id', 'event_key', name='uq_notification_delivery_identity_event')" in model
    assert "ondelete='RESTRICT'" in model
    assert "down_revision = '20261023_notify_retry_after'" in migration
    assert "UniqueConstraint('source_delivery_id', name='uq_notification_delivery_identities_source_delivery_id')" in model
    assert "name='uq_notification_delivery_identities_source_delivery_id'" in migration
    assert "op.create_table(" in migration
    assert "'notification_delivery_identities'" in migration
    model_exports = read('app/models/__init__.py')
    assert 'NotificationDeliveryIdentity' in model_exports
    assert 'NotificationDeliveryIdentity' not in service
    assert 'cleanup_supported = False' in adapter


def test_notification_delivery_cold_archive_is_protected_until_durable_retention_approval() -> None:
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    worker = read('app/platform_operations/data_lifecycle/retention/tasks.py')
    assert "if domain_name == 'notification_delivery' and not dry_run:" in engine
    assert "if domain.name == 'notification_delivery':" in engine
    assert "trigger_type not in {'manual', 'cli'}" in engine
    assert "stored_policy.operation_mode != 'archive_only'" in engine
    assert "if domain_name in {'audit_event', 'notification_delivery'}:" in worker
    assert "'scheduling_not_admitted'" in worker
    assert "'archive_purge'] = {'status': 'not_admitted'" in worker
