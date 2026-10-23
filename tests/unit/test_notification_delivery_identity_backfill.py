"""Guard bounded Notification Delivery ledger backfill before runtime admission."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.integrations.delivery.notification_channels.identity_backfill import (
    MAX_BACKFILL_BATCH_SIZE,
    _normalized_time,
    reconcile_delivery_identity_batch,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ('high_watermark', 'after_id', 'batch_size'),
    [
        (-1, 0, 250),
        (5, -1, 250),
        (5, 6, 250),
        (5, 0, 0),
        (5, 0, 1001),
    ],
)
def test_identity_backfill_rejects_invalid_windows_before_database_access(
    high_watermark: int, after_id: int, batch_size: int,
) -> None:
    with pytest.raises(ValueError):
        reconcile_delivery_identity_batch(
            high_watermark=high_watermark,
            after_id=after_id,
            batch_size=batch_size,
        )


def test_identity_backfill_normalizes_naive_utc_and_aware_timestamps() -> None:
    naive = datetime(2026, 10, 23, 7, 0, 0)
    aware = naive.replace(tzinfo=UTC)
    assert _normalized_time(naive) == aware
    assert _normalized_time(aware + timedelta(hours=1)) == aware + timedelta(hours=1)


def test_backfill_is_not_connected_to_transport_or_automatic_cleanup() -> None:
    assert MAX_BACKFILL_BATCH_SIZE == 1000
    source = (ROOT / 'app/integrations/delivery/notification_channels/identity_backfill.py').read_text()
    transport = (ROOT / 'app/integrations/delivery/notification_channels/service.py').read_text()
    archive = (ROOT / 'app/platform_operations/data_lifecycle/retention/domains/notification_delivery.py').read_text()
    assert 'apply: bool = False' in source
    assert 'high_watermark: int' in source
    assert 'after_id: int = 0' in source
    assert '.limit(batch_size + 1)' in source
    assert 'statement.on_conflict_do_nothing(' in source
    assert 'Concurrent identity conflict; rolling back backfill page.' in source
    assert 'db.session.rollback()' in source
    assert 'db.session.commit()' in source
    assert 'IdentityBackfill' not in transport
    assert 'reconcile_delivery_identity_batch' not in transport
    assert 'cleanup_supported = False' in archive
    assert 'NotificationDelivery.query.delete(' not in source
