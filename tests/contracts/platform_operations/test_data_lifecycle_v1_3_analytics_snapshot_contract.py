from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_snapshots_are_a_registered_lifecycle_domain() -> None:
    registry = read('app/retention/domains/__init__.py')
    adapter = read('app/retention/domains/analytics_snapshot.py')

    assert 'from app.retention.domains.analytics_snapshot import AnalyticsSnapshotArchiveDomain' in registry
    assert "'analytics_snapshot': AnalyticsSnapshotArchiveDomain" in registry
    assert "name = 'analytics_snapshot'" in adapter
    assert "source_model = 'analytics_snapshots'" in adapter


def test_analytics_snapshot_cleanup_preserves_pending_and_serveable_rows() -> None:
    adapter = read('app/retention/domains/analytics_snapshot.py')

    assert "AnalyticsSnapshot.status != 'pending'" in adapter
    assert "if snapshot.status == 'pending':" in adapter
    assert 'stale_deadline = expires_at + timedelta(' in adapter
    assert 'return stale_deadline < cutoff_at' in adapter
    assert 'safe_ids = [row.id for row in rows if _eligible_for_boundary(row, cutoff_at=cutoff_at)]' in adapter
    assert "'payload': row.payload_json" in adapter
    assert "'last_job_execution_id': row.last_job_execution_id" in adapter


def test_analytics_snapshot_policy_is_scheduled_on_existing_maintenance_boundary() -> None:
    config = read('app/config/default.py')
    tasks = read('app/retention/tasks.py')
    policy = read('app/retention/policy_service.py')

    assert "'analytics_snapshot'" in tasks
    assert 'ANALYTICS_SNAPSHOT_RETENTION_ENABLED' in config
    assert 'ANALYTICS_SNAPSHOT_RETENTION_DAYS' in config
    assert 'ANALYTICS_SNAPSHOT_ARCHIVE_RETENTION_DAYS' in config
    assert 'ANALYTICS_SNAPSHOT_RETENTION_BATCH_SIZE' in config
    assert "if domain == 'analytics_snapshot':" in policy
    assert "ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_HOUR" in policy
    assert "ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_MINUTE" in policy


def test_analytics_snapshot_lifecycle_is_explained_in_data_lifecycle_ui() -> None:
    presentation = read('app/retention/presentation.py')
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')

    assert "'analytics_snapshot': 'Analytics Snapshots'" in presentation
    assert "'label': 'Analytics Materialization'" in presentation
    assert "'label': 'Forecast History'" in presentation
    assert "'label': 'Dashboard Evidence'" in presentation
    assert "selected.name == 'analytics_snapshot'" in workspace
    assert 'Serve Window Protection' in workspace


def test_analytics_snapshot_lifecycle_v1_3_is_locked() -> None:
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_3.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_3_AUDIT_2026_08_08.md').exists()
