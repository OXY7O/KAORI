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
    assert 'with_scan_overview=True' in collector


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
