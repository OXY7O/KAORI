from app.integrations.kernel.registry import (
    IntegrationImplementation,
    IntegrationRegistry,
    get_integration,
)


class _SyntheticRegistryAdapter:
    integration_type = 'registry'

    def execute(self, operation, instance, **kwargs):
        return {'operation': operation, 'instance': instance, **kwargs}

    def get_state(self, instance, *, validation_result=None):
        return {'instance': instance, 'validation_result': validation_result}


def test_second_registry_provider_registers_without_harbor_code_changes() -> None:
    local = IntegrationRegistry()
    local.register(get_integration('registry'))
    synthetic = IntegrationImplementation(
        integration_type='registry',
        provider_key='aws_ecr',
        adapter_key='aws_ecr_api',
        adapter=_SyntheticRegistryAdapter(),
        instance_loader=lambda _record_id: None,
        canonical_record_loader=lambda _canonical_id: None,
        module_path='tests.synthetic_registry_provider',
    )

    local.register_implementation(synthetic)

    resolved = local.get_implementation('registry', 'aws_ecr')
    assert resolved.provider_key == 'aws_ecr'
    assert resolved.adapter_key == 'aws_ecr_api'
    assert resolved.integration_type == 'registry'


def _synthetic_inventory(_instance: object):
    from app.integrations.registry.contracts import (
        ArtifactRecord,
        ProjectRecord,
        RegistryInventoryEvidence,
        RepositoryRecord,
    )

    artifact = ArtifactRecord(
        digest='sha256:' + 'a' * 64,
        provider_native_id='external-993',
        artifact_type='OCI',
        media_type='application/vnd.oci.image.manifest.v1+json',
        size_bytes=321,
        push_time=None,
        pull_time=None,
        tags=[{'name': 'stable'}],
    )
    repository = RepositoryRecord(
        name='team/service',
        provider_native_id='repo-1',
        artifact_count=1,
        pull_count=None,
        description=None,
        provider_created_at=None,
        provider_updated_at=None,
        artifacts=[artifact],
    )
    return RegistryInventoryEvidence(
        projects=[
            ProjectRecord(
                name='team',
                provider_native_id='tenant-3',
                public=False,
                repository_count=1,
                repositories=[repository],
            )
        ]
    )


def test_second_registry_collector_normalizes_to_canonical_evidence(monkeypatch) -> None:
    from app.artifact_registry.contracts import RegistryInventoryEvidence as ConsumerEvidence
    from app.integrations.registry import collectors
    from app.integrations.registry.collectors import RegistryInventoryCollector

    monkeypatch.setitem(
        collectors._COLLECTORS,
        'aws_ecr',
        RegistryInventoryCollector(provider_key='aws_ecr', collect=_synthetic_inventory),
    )
    evidence = collectors.get_registry_collector('aws_ecr').collect(object())
    assert isinstance(evidence, ConsumerEvidence)
    project = evidence.projects[0]
    assert project.name == 'team'
    assert project.repositories[0].name == 'team/service'
    artifact = project.repositories[0].artifacts[0]
    assert artifact.digest == 'sha256:' + 'a' * 64
    assert artifact.provider_native_id == 'external-993'
    assert artifact.tags == [{'name': 'stable'}]


def test_second_registry_optional_security_governance_collectors_are_independent(
    monkeypatch,
) -> None:
    from app.integrations.registry import governance_contracts, security_collectors
    from app.integrations.registry.governance_contracts import (
        RegistryGovernanceCollector,
        RegistryGovernanceEvidence,
    )
    from app.integrations.registry.security_collectors import RegistrySecurityCollector
    from app.integrations.registry.security_contracts import RegistrySecurityEvidence

    monkeypatch.setitem(
        security_collectors._COLLECTORS,
        'aws_ecr',
        RegistrySecurityCollector(
            provider_key='aws_ecr',
            collect=lambda _instance, _targets, _progress, _current: RegistrySecurityEvidence(),
            capabilities=frozenset(),
        ),
    )
    monkeypatch.setitem(
        governance_contracts._COLLECTORS,
        'aws_ecr',
        RegistryGovernanceCollector(
            provider_key='aws_ecr',
            collect=lambda _instance: RegistryGovernanceEvidence(),
        ),
    )
    assert (
        security_collectors.get_registry_security_collector('aws_ecr')
        .collect(
            object(),
            [],
            None,
            None,
        )
        .artifacts
        == []
    )
    assert governance_contracts.get_registry_governance_collector('aws_ecr').collect(object()).projects == []


def test_unknown_optional_collector_fails_explicitly_not_harbor_fallback() -> None:
    import pytest

    from app.integrations.registry.governance_contracts import get_registry_governance_collector
    from app.integrations.registry.security_collectors import get_registry_security_collector

    with pytest.raises(LookupError, match='No qualified'):
        get_registry_security_collector('synthetic_unknown')
    with pytest.raises(LookupError, match='No qualified'):
        get_registry_governance_collector('synthetic_unknown')


def test_artifact_registry_consumers_use_canonical_digest_not_harbor_identifiers() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    commit = (root / 'app/artifact_registry/sync.py').read_text(encoding='utf-8')
    correlation = (root / 'app/artifact_registry/correlation.py').read_text(encoding='utf-8')
    collectors = (root / 'app/artifact_registry/collectors.py').read_text(encoding='utf-8')
    assert 'existing = {artifact.digest: artifact for artifact in repository.artifacts}' in commit
    assert 'get_registry_collector(identity.provider_key)' in commit
    assert 'if image.digest == artifact.digest:' in correlation
    assert 'image.digest == candidate.digest else None' in correlation
    assert "return 'digest', 'strong'" in correlation
    assert 'from app.integrations.registry.collectors import' in collectors
    assert "if provider_key == 'harbor'" not in commit
