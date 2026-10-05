from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_registry_inventory_remains_bounded_to_inventory_evidence() -> None:
    harbor_inventory = (
        ROOT / 'app/integrations/registry/providers/harbor/inventory.py'
    ).read_text()
    inventory_task = (ROOT / 'app/artifact_registry/tasks.py').read_text()
    inventory_sync = (ROOT / 'app/artifact_registry/sync.py').read_text()

    assert 'get_vulnerability_report' not in harbor_inventory
    assert 'sync_registry_governance' not in inventory_task
    assert 'refresh_registry_workload_bindings' not in inventory_sync


def test_registry_security_is_incremental_and_independent() -> None:
    harbor_security = (
        ROOT / 'app/integrations/registry/providers/harbor/security.py'
    ).read_text()
    security_jobs = (
        ROOT / 'app/artifact_registry/security/sync_jobs.py'
    ).read_text()
    registered_jobs = (
        ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'
    ).read_text()

    assert 'list_all_artifacts(' in harbor_security
    assert 'with_scan_overview=True' in harbor_security
    assert 'if scan is not None and changed:' in harbor_security
    assert 'get_vulnerability_report(' in harbor_security
    assert 'reuse_existing_scan' in harbor_security
    assert 'artifact_registry.security.sync' in registered_jobs
    assert 'artifact-registry-security:global' in security_jobs
    assert 'require_registered_worker=True' in security_jobs


def test_registry_governance_and_runtime_correlation_are_separate_jobs() -> None:
    jobs = (
        ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'
    ).read_text()
    governance_task = (ROOT / 'app/artifact_registry/governance_tasks.py').read_text()
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    correlation_jobs = (
        ROOT / 'app/artifact_registry/correlation_sync_jobs.py'
    ).read_text()

    assert 'artifact_registry.governance.sync' in jobs
    assert 'artifact_registry.runtime_correlation.materialize' in jobs
    assert 'sync_registry_governance' in governance_task
    assert 'filter_current_generation(' in correlation
    assert 'materialization_session.query(PodInventory)' in correlation
    assert 'require_registered_worker=True' in correlation_jobs


def test_global_sync_all_inventory_does_not_fan_out_registry_non_inventory_work() -> None:
    routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text()

    assert "job_keys.append('artifact_registry.inventory.sync')" in routes
    assert "job_keys.append('artifact_registry.security.sync')" not in routes
    assert "job_keys.append('artifact_registry.governance.sync')" not in routes
    assert "job_keys.append('artifact_registry.runtime_correlation.materialize')" not in routes


def test_registry_worker_task_registration_matches_separated_jobs() -> None:
    config = (ROOT / 'app/config/default.py').read_text()

    for task in (
        'app.artifact_registry.tasks.sync_all_registry',
        'app.artifact_registry.security.tasks.sync_all_registry_security',
        'app.artifact_registry.governance_tasks.sync_all_registry_governance',
        'app.artifact_registry.correlation_tasks.materialize_registry_runtime_correlation',
    ):
        assert task in config

def test_harbor_security_uses_scan_completion_as_primary_incremental_marker() -> None:
    harbor_security = (
        ROOT / 'app/integrations/registry/providers/harbor/security.py'
    ).read_text()

    identity = harbor_security.split('def _scan_identity_changed', 1)[1].split(
        'def collect_harbor_security',
        1,
    )[0]
    assert 'target.scan_completed_at is not None or scan_completed_at is not None' in identity
    assert 'return target.scan_completed_at != scan_completed_at' in identity


def test_registry_evidence_jobs_fail_terminally_when_every_provider_fails() -> None:
    inventory_task = (ROOT / 'app/artifact_registry/tasks.py').read_text()
    security_task = (ROOT / 'app/artifact_registry/security/tasks.py').read_text()
    governance_task = (ROOT / 'app/artifact_registry/governance_tasks.py').read_text()

    assert 'All eligible Registry providers failed inventory synchronization.' in inventory_task
    assert 'All eligible Registry providers failed security synchronization.' in security_task
    assert 'All eligible Registry providers failed governance synchronization.' in governance_task
    assert "context.fail(" in inventory_task
    assert "context.fail(" in security_task
    assert "context.fail(" in governance_task

