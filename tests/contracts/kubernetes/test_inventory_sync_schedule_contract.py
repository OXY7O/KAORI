from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_inventory_schedule_is_registered_and_database_backed() -> None:
    model = _source('app/models/job.py')
    migration = _source('migrations/versions/20260724_job_orchestration.py')
    config = _source('app/config/default.py')
    definition = _source('app/jobs/definitions/inventory_sync.py')

    assert "__tablename__ = 'job_policies'" in model
    assert "'kubernetes.inventory.sync'" in definition
    assert "'app.jobs.tasks.dispatch_scheduled_jobs'" in config
    assert "crontab(minute='*')" in config
    assert "'job_policies'" in migration


def test_scheduled_and_manual_fleet_sync_share_registered_dispatch() -> None:
    scheduler = _source('app/jobs/scheduler.py')
    quick_sync = _source('app/cluster/quick_sync.py')
    sync_jobs = _source('app/cluster/sync_jobs.py')

    assert 'dispatch_registered_job(' in scheduler
    assert "job_key='kubernetes.inventory.sync'" in quick_sync
    assert 'enqueue_canonical_job(' in sync_jobs
    assert "resource_group='kubernetes-inventory:global'" in sync_jobs


def test_schedule_claim_and_inventory_commit_boundaries_are_explicit() -> None:
    scheduler = _source('app/jobs/scheduler.py')
    synchronization = _source('app/inventory/synchronization.py')

    assert '.with_for_update(skip_locked=True)' in scheduler
    assert 'policy.next_run_at = now + timedelta' in scheduler
    assert '_lock_cluster_inventory_sync(' in synchronization
    assert 'db.session.commit()' in synchronization
    assert 'db.session.rollback()' in synchronization


def test_fleet_targets_use_canonical_kubernetes_resolution() -> None:
    sync_jobs = _source('app/cluster/sync_jobs.py')

    assert 'connection_for_cluster(cluster)' in sync_jobs
    assert 'Skipping cluster %s from fleet inventory sync' in sync_jobs
    assert 'KubernetesConnection.query' not in sync_jobs


def test_quick_action_wording_describes_inventory_scope() -> None:
    navbar = _source('app/templates/components/navigation/navbar.html')

    assert 'Sync All Inventory' in navbar
    assert 'complete inventory refresh' in navbar


def test_registered_inventory_dispatch_supports_recovery_for_one_cluster() -> None:
    adapter = _source('app/inventory/job_adapter.py')
    recovery = _source('app/integrations/runtime/recovery.py')

    assert "cluster_id = str((parameters or {}).get('cluster_id') or '').strip()" in adapter
    assert 'enqueue_cluster_inventory_sync(' in adapter
    assert "_INVENTORY_JOB_KEY = 'kubernetes.inventory.sync'" in recovery
    assert "parameters={'cluster_id': cluster_id}" in recovery
    assert 'from app.cluster.sync_jobs import enqueue_cluster_inventory_sync' not in recovery
