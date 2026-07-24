from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_inventory_schedule_is_enabled_by_default_and_database_backed() -> None:
    model = _source('app/models/inventory_sync.py')
    migration = _source('migrations/versions/20260724_inventory_sync_policy.py')
    config = _source('app/config/default.py')

    assert 'default=True' in model
    assert "server_default=sa.true()" in migration
    assert "'app.inventory.tasks.dispatch_scheduled_inventory_sync'" in config
    assert "crontab(minute='*')" in config


def test_scheduled_and_manual_fleet_sync_share_the_canonical_dispatcher() -> None:
    schedule = _source('app/inventory/schedule.py')
    routes = _source('app/cluster/routes.py')
    sync_jobs = _source('app/cluster/sync_jobs.py')

    assert "enqueue_all_cluster_inventory_sync(requested_by_user_id=None, trigger_type='scheduled')" in schedule
    assert 'enqueue_all_cluster_inventory_sync(' in routes
    assert 'enqueue_canonical_job(' in sync_jobs
    assert "resource_group='kubernetes-inventory:global'" in sync_jobs


def test_schedule_claim_and_inventory_commit_boundaries_are_explicit() -> None:
    schedule = _source('app/inventory/schedule.py')
    synchronization = _source('app/inventory/synchronization.py')

    assert '.with_for_update()' in schedule
    assert 'policy.next_run_at = now + timedelta' in schedule
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
