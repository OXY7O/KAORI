from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.storage.object_storage.inventory.presentation import (
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
        'protection_assessed': 2,
        'public_exposure': 1,
        'exposure_assessed': 2,
        'usage_collected': 1,
    }

    readings = _overview_fleet_readings(posture)
    assert readings[0]['title'] == '2/2 Quota Assessed'
    assert readings[1]['title'] == '1 Protection Attention'
    assert readings[2]['title'] == '1 Public Exposure'
    assert readings[3]['title'] == '1/2 Usage Collected'


def test_unassessed_protection_and_exposure_never_project_green_clean_fleet_state() -> None:
    missing = _BucketPostureStub(
        quota_state='not_collected',
        versioning_state='not_collected',
        immutability_state='not_collected',
        encryption_state='not_collected',
        exposure_state='not_collected',
        usage_stats_state='not_collected',
    )
    posture = _overview_bucket_posture([missing])
    assert posture['protection_assessed'] == 0
    assert posture['exposure_assessed'] == 0
    readings = _overview_fleet_readings(posture)
    assert readings[1]['tone'] == 'unknown'
    assert readings[2]['tone'] == 'unknown'
    assert 'Not Assessed' in readings[1]['title']
    assert 'Not Assessed' in readings[2]['title']


def test_partial_exposure_coverage_is_warning_even_with_zero_public_assets() -> None:
    assessed = _BucketPostureStub('configured', 'enabled', 'enabled', 'enabled', 'private', 'collected')
    missing = _BucketPostureStub('not_collected', 'not_collected', 'not_collected', 'not_collected', 'unknown', 'not_collected')
    posture = _overview_bucket_posture([assessed, missing])
    assert posture['protection_assessed'] == 1
    assert posture['exposure_assessed'] == 1
    readings = _overview_fleet_readings(posture)
    assert readings[1]['tone'] == 'warning'
    assert readings[2]['tone'] == 'warning'
    assert '1/2' in readings[2]['description']


def test_complete_nonpublic_protection_evidence_retains_normal_tone() -> None:
    assessed = _BucketPostureStub('configured', 'enabled', 'enabled', 'enabled', 'private', 'collected')
    readings = _overview_fleet_readings(_overview_bucket_posture([assessed]))
    assert readings[1]['title'] == 'No Protection Attention'
    assert readings[1]['tone'] == 'normal'
    assert readings[2]['title'] == 'No Public Exposure'
    assert readings[2]['tone'] == 'normal'


def test_no_assets_or_public_evidence_keeps_unknown_state_and_real_public_attention() -> None:
    empty = _overview_fleet_readings(_overview_bucket_posture([]))
    assert empty[1]['tone'] == empty[2]['tone'] == 'unknown'
    public = _BucketPostureStub('configured', 'enabled', 'enabled', 'enabled', 'public', 'collected')
    readings = _overview_fleet_readings(_overview_bucket_posture([public]))
    assert readings[1]['tone'] == 'warning'  # Public exposure also triggers protection attention.
    assert readings[2]['tone'] == 'critical'
