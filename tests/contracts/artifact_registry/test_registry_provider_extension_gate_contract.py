from pathlib import Path

from app.artifact_registry.collectors import (
    RegistryInventoryCollector,
    get_registry_collector,
    register_registry_collector,
)
from app.artifact_registry.contracts import RegistryInventoryEvidence

ROOT = Path(__file__).resolve().parents[3]


def test_synthetic_second_provider_collector_uses_shared_contract() -> None:
    collector = RegistryInventoryCollector(
        provider_key='synthetic_registry_test',
        collect=lambda _record: RegistryInventoryEvidence(
            projects=[],
            provider_metadata={'source': 'synthetic'},
        ),
    )
    register_registry_collector(collector, replace=True)

    resolved = get_registry_collector('synthetic_registry_test')
    evidence = resolved.collect(object())

    assert resolved.provider_key == 'synthetic_registry_test'
    assert evidence.projects == []
    assert evidence.provider_metadata['source'] == 'synthetic'


def test_generic_registry_paths_do_not_import_harbor_models_or_clients() -> None:
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    jobs = (ROOT / 'app/artifact_registry/sync_jobs.py').read_text()
    tasks = (ROOT / 'app/artifact_registry/tasks.py').read_text()

    for content in (sync, correlation, jobs, tasks):
        assert 'HarborInstance' not in content
        assert 'providers.harbor' not in content

    harbor_collector = (ROOT / 'app/integrations/registry/providers/harbor/inventory.py').read_text()
    assert 'collect_harbor_inventory' in harbor_collector
    assert 'RegistryInventoryEvidence' in harbor_collector


def test_provider_matrix_declares_future_registry_extension_slots() -> None:
    matrix = (ROOT / 'app/definitions/catalogs/integrations/provider_matrix.yaml').read_text()
    for provider in (
        'aws_ecr',
        'google_artifact_registry',
        'azure_container_registry',
        'github_container_registry',
        'oci_distribution',
    ):
        assert f'- key: {provider}' in matrix
    assert matrix.count('lifecycle: planned') >= 5
