from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_registry_inventory_is_provider_neutral_and_digest_oriented() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    assert 'class RegistryProject' in models
    assert 'class RegistryRepository' in models
    assert 'class RegistryArtifact' in models
    assert 'class RegistryTag' in models
    assert "UniqueConstraint('repository_id', 'digest'" in models
    assert 'HarborProject' not in models
    assert 'HarborRepository' not in models
    assert 'HarborArtifact' not in models


def test_registry_operational_pages_read_committed_state() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    assert 'RegistryProject.query' in presentation
    assert 'RegistryArtifact.query' in presentation
    assert 'build_client' not in presentation
    assert 'requests.' not in routes


def test_harbor_is_collector_not_operational_page_authority() -> None:
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    collector = (ROOT / 'app/integrations/registry/providers/harbor/inventory.py').read_text()
    client = (ROOT / 'app/integrations/registry/providers/harbor/client.py').read_text()

    assert 'get_registry_collector' in sync
    assert 'commit_registry_inventory' in sync
    assert 'HarborInstance' not in sync
    assert 'collect_harbor_inventory' in collector
    assert 'RegistryInventoryEvidence' in collector
    assert 'list_all_artifacts' in client
    assert 'get_vulnerability_report' not in collector
    assert 'with_scan_overview=True' not in collector
    assert 'with_sbom_overview=True' not in collector
    assert 'with_signature=True' not in collector
    assert 'with_immutable_status=True' not in collector


def test_registry_inventory_sync_uses_operational_read_contract_eligibility() -> None:
    eligibility = (ROOT / 'app/artifact_registry/eligibility.py').read_text()
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    sync_jobs = (ROOT / 'app/artifact_registry/sync_jobs.py').read_text()

    assert "normalized_readiness == 'ready'" in eligibility
    assert "normalized_readiness == 'degraded'" in eligibility
    assert "normalized_compatibility == 'compatible_with_warnings'" in eligibility
    assert "unverified_version" not in eligibility.split('def inventory_read_contract_eligible', 1)[1].split('def registry_inventory_eligibility', 1)[0]
    assert 'registry_inventory_eligibility(identity, provider_record=provider_record)' in sync
    assert "identity.readiness_status != 'ready'" not in sync
    assert 'registry_inventory_eligibility(identity)' in sync_jobs
    assert "IntegrationInstance.readiness_status == 'ready'" not in sync_jobs


def test_global_sync_all_inventory_includes_artifact_registry() -> None:
    routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text()
    navbar = (ROOT / 'app/templates/components/navigation/navbar.html').read_text()

    assert "current_user.has_permission('artifact_registry.sync')" in routes
    assert "job_keys.append('artifact_registry.inventory.sync')" in routes
    assert (
        "can_sync_artifact_registry_inventory = "
        "current_user.has_permission('artifact_registry.sync')"
    ) in navbar
    assert (
        'can_sync_kubernetes_inventory or can_sync_object_storage_inventory or '
        'can_sync_artifact_registry_inventory'
    ) in navbar


def test_registry_inventory_worker_registration_matches_dispatch_contract() -> None:
    config = (ROOT / 'app/config/default.py').read_text()
    sync_jobs = (ROOT / 'app/artifact_registry/sync_jobs.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()

    assert "'app.artifact_registry.tasks'," in config
    assert "'app.artifact_registry.tasks.sync_all_registry': {" in config
    registry_route = config.split(
        "'app.artifact_registry.tasks.sync_all_registry': {",
        1,
    )[1].split('},', 1)[0]
    assert "'queue': 'inventory'" in registry_route

    assert 'JobDispatchOptions' in sync_jobs
    assert sync_jobs.count('require_registered_worker=True') >= 2
    assert 'JobWorkerUnavailable' in routes
    assert 'Artifact Registry Worker Unavailable' in routes

def test_registry_inventory_worker_does_not_cross_into_other_registry_workstreams() -> None:
    task = (ROOT / 'app/artifact_registry/tasks.py').read_text()
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()

    assert 'sync_registry_governance' not in task
    assert 'refresh_registry_workload_bindings' not in sync

