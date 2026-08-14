from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.inventory.object_storage.presentation import (
    OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS,
    _inventory_guidance,
    _inventory_signals,
    _is_stale,
    _overview_bucket_posture,
    _overview_fleet_readings,
    _snapshot_status,
)


@dataclass(frozen=True)
class _BucketPostureStub:
    quota_state: str
    versioning_state: str
    immutability_state: str
    encryption_state: str
    exposure_state: str
    usage_stats_state: str


def test_snapshot_status_distinguishes_current_stale_and_missing() -> None:
    now = datetime.now(UTC)
    assert _snapshot_status(None) == ('Not Collected', 'warning')
    assert _snapshot_status(now) == ('Current', 'normal')
    assert _snapshot_status(now - timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS + 1)) == (
        'Stale',
        'warning',
    )


def test_is_stale_accepts_naive_database_timestamps() -> None:
    now = datetime.now(UTC)
    naive_old = (now - timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS + 1)).replace(tzinfo=None)
    assert _is_stale(naive_old, now=now) is True


def test_inventory_signals_keep_provider_and_snapshot_conditions_explicit() -> None:
    row = {
        'status_tone': 'critical',
        'last_inventory_at': None,
    }
    signals = _inventory_signals(row)
    labels = {signal['label'] for signal in signals}
    assert labels == {'Provider Attention', 'Inventory Not Collected'}
    guidance = _inventory_guidance(row, signals)
    assert guidance['title'] == 'Review Provider Readiness'


def test_overview_bucket_posture_separates_quota_protection_exposure_and_usage() -> None:
    buckets = [
        _BucketPostureStub(
            quota_state='configured',
            versioning_state='enabled',
            immutability_state='enabled',
            encryption_state='configured',
            exposure_state='private',
            usage_stats_state='collected',
        ),
        _BucketPostureStub(
            quota_state='not_configured',
            versioning_state='enabled',
            immutability_state='not_configured',
            encryption_state='not_configured',
            exposure_state='public',
            usage_stats_state='not_collected',
        ),
    ]

    posture = _overview_bucket_posture(buckets)
    assert posture == {
        'total_assets': 2,
        'quota_assessed': 2,
        'quota_configured': 1,
        'quota_gaps': 0,
        'protection_attention': 1,
        'public_exposure': 1,
        'usage_collected': 1,
    }

    readings = _overview_fleet_readings(posture)
    assert readings[0]['title'] == '2/2 Quota Assessed'
    assert readings[1]['title'] == '1 Protection Attention'
    assert readings[2]['title'] == '1 Public Exposure'
    assert readings[3]['title'] == '1/2 Usage Collected'
