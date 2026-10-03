from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_harbor_provider_is_registered_under_registry_domain() -> None:
    provider = read('app/integrations/registry/providers/harbor/__init__.py')
    taxonomy = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    matrix = read('app/definitions/catalogs/integrations/provider_matrix.yaml')

    assert "integration_type='registry'" in provider
    assert "domain_key='registry'" in provider
    assert "capability_key='registry'" in provider
    assert "provider_key='harbor'" in provider
    assert "adapter_key='harbor_api_v2'" in provider
    assert 'key: registry' in taxonomy
    assert 'workspace_endpoint: integrations.registry' in taxonomy
    assert 'key: harbor' in matrix
    assert 'protocol: harbor_api_v2' in matrix


def test_harbor_foundation_exposes_no_provider_mutation_operations() -> None:
    provider = read('app/integrations/registry/providers/harbor/__init__.py')
    client = read('app/integrations/registry/providers/harbor/client.py')

    for operation in (
        'artifact.delete',
        'repository.delete',
        'project.delete',
        'retention.update',
        'immutability.update',
        'replication.trigger',
        'garbage_collection.trigger',
        'scan.trigger',
        'robot.create',
        'user.create',
    ):
        assert operation not in provider

    assert 'requests.post(' not in client
    assert 'requests.put(' not in client
    assert 'requests.patch(' not in client
    assert 'requests.delete(' not in client
    assert 'requests.get(' in client


def test_harbor_credential_material_is_encrypted_and_not_part_of_validation_evidence() -> None:
    model = read('app/models/harbor.py')
    validation = read('app/integrations/registry/providers/harbor/validation.py')
    contracts = read('app/integrations/registry/providers/harbor/contracts.py')

    assert "password: Mapped[str | None] = mapped_column(EncryptedText()" in model
    assert "'password'" not in validation
    result_dict = contracts.split('class ValidationResult', 1)[1]
    assert "'password'" not in result_dict
    assert "'username'" not in result_dict
