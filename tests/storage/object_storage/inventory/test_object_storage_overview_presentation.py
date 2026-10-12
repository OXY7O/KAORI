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


def test_sql_fleet_bucket_aggregate_matches_existing_pure_posture(monkeypatch) -> None:
    from types import SimpleNamespace

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
    from app.storage.object_storage.inventory import aggregates

    engine = create_engine('sqlite+pysqlite:///:memory:')
    ObjectStorageSystem.__table__.create(engine)
    ObjectStorageBucket.__table__.create(engine)
    with Session(engine) as session:
        monkeypatch.setattr(aggregates, 'db', SimpleNamespace(session=session))
        assert aggregates.bucket_fleet_posture() == _overview_bucket_posture([])
        session.add(ObjectStorageSystem(id='storage-a', name='Storage A', environment='uat', status='ready'))
        samples = [
            _BucketPostureStub('configured', 'enabled', 'enabled', 'configured', 'private', 'collected'),
            _BucketPostureStub(
                'not_configured', 'not_collected', 'not_collected', 'not_collected',
                'unknown', 'not_collected',
            ),
            _BucketPostureStub('not_collected', 'disabled', 'enabled', 'enabled', 'restricted', 'collected'),
            _BucketPostureStub('configured', 'enabled', 'enabled', 'enforced', 'public', 'not_collected'),
            _BucketPostureStub(
                'not_collected', 'enabled', 'not_supported', 'enabled',
                'not_collected', 'not_collected',
            ),
        ]
        for index, data in enumerate(samples, start=1):
            session.add(ObjectStorageBucket(
                id=index, name=f'bucket-{index}', object_storage_system_id='storage-a',
                quota_state=data.quota_state, versioning_state=data.versioning_state,
                immutability_state=data.immutability_state, encryption_state=data.encryption_state,
                exposure_state=data.exposure_state, usage_stats_state=data.usage_stats_state,
                observed_at=datetime.now(UTC),
            ))
        session.commit()
        assert aggregates.bucket_fleet_posture() == _overview_bucket_posture(samples)
        assert aggregates.bucket_usage_summary()['buckets'] == len(samples)
        assert aggregates.bucket_usage_summary(system_id='nonexistent')['buckets'] == 0
    engine.dispose()


def test_inventory_overview_aggregates_without_loading_entire_bucket_collection() -> None:
    from pathlib import Path

    source = Path('app/storage/object_storage/inventory/presentation.py').read_text(encoding='utf-8')
    overview = source.split('def build_overview()', 1)[1].split('class SystemFilters:', 1)[0]
    assert 'bucket_fleet_posture()' in overview
    assert '_system_scope().order_by(None)' in overview
    assert '_overview_snapshot_from_counts(' in overview
    assert 'ObjectStorageBucket.query.all()' not in overview
    assert '_system_query().all()' not in overview
    assert '_system_row(' not in overview


def test_storage_inventory_system_row_qualifies_source_changed_evidence() -> None:
    from types import SimpleNamespace

    from app.storage.object_storage.inventory.presentation import _system_row

    observed = datetime.now(UTC)
    system = SimpleNamespace(
        id='system-1', name='System One', description=None, environment='uat',
        status='unknown', buckets=[SimpleNamespace(name='prior-bucket')],
        inventory_observed_at=observed,
    )
    connection = SimpleNamespace(
        id=7, declared_release=None, endpoint='https://s3.example.invalid',
        region='us-east-1', addressing_style='path', compatibility_profile=None,
        readiness_status='validation_required', last_validated_at=None, last_checked_at=None,
    )
    metadata = {'object_storage_connection_generation': 2, 'object_storage_inventory_generation': 1}
    owner = SimpleNamespace(
        identity=SimpleNamespace(metadata_json=metadata), record=connection,
        provider_key='minio', provider=SimpleNamespace(label='MinIO'),
    )
    row = _system_row(system, owner=owner, owner_resolved=True)
    assert row['inventory_source_changed'] is True
    assert row['sync_status_label'] == 'Source Changed'
    assert row['sync_status_tone'] == 'warning'
    assert row['snapshot_source'] == 'Last-Known Snapshot'
    assert row['guidance']['title'] == 'Revalidate Storage Source'
    assert row['bucket_count'] == 1  # Historical count, not a new-source zero.

    owner.identity.metadata_json['object_storage_inventory_generation'] = 2
    current = _system_row(system, owner=owner, owner_resolved=True)
    assert current['inventory_source_changed'] is False
    assert current['snapshot_source'] == 'Committed Snapshot'

    system.inventory_observed_at = None
    owner.identity.metadata_json['object_storage_connection_generation'] = 3
    absent = _system_row(system, owner=owner, owner_resolved=True)
    assert absent['inventory_source_changed'] is False
    assert absent['sync_status_label'] == 'Not Collected'
