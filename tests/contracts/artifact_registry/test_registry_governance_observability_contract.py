from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_registry_governance_is_committed_and_provider_neutral() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    governance = (ROOT / 'app/artifact_registry/governance.py').read_text()
    harbor = (ROOT / 'app/integrations/registry/providers/harbor/governance.py').read_text()

    assert 'class RegistryGovernanceState' in models
    assert 'class RegistryProjectGovernance' in models
    assert 'class RegistryReplicationPolicy' in models
    assert 'HarborInstance' not in governance
    assert 'RegistryGovernanceCollector' in governance
    assert 'collect_harbor_governance' in harbor
    assert 'retention_status' in harbor
    assert 'immutability_status' in harbor
    assert 'ReplicationPolicyRecord' in harbor


def test_registry_metrics_reuses_canonical_metrics_source_binding() -> None:
    taxonomy = (ROOT / 'app/definitions/catalogs/integrations/taxonomy.yaml').read_text()
    metrics_contract = (
        ROOT / 'app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml'
    ).read_text()
    validators = (
        ROOT / 'app/integrations/observability/metrics_source/binding_validators/__init__.py'
    ).read_text()
    registry_validator = (
        ROOT / 'app/integrations/observability/metrics_source/binding_validators/registry_asset.py'
    ).read_text()

    assert 'asset_type: registry_instance' in taxonomy
    assert 'asset_type: registry_instance' in metrics_contract
    assert 'profile_key: registry-metrics-v1' in metrics_contract
    assert "register_binding_validator(PROMETHEUS_HTTP_ADAPTER, 'registry_instance'" in validators
    assert 'IntegrationBinding' in registry_validator
    assert 'RegistryHarborMetricsAuditor' in registry_validator


def test_artifact_registry_has_no_direct_prometheus_transport() -> None:
    for path in (ROOT / 'app/artifact_registry').glob('*.py'):
        content = path.read_text()
        assert 'requests.get(' not in content
        assert '/api/v1/query' not in content
        assert 'prometheus' not in content.lower() or path.name == 'observability.py'


def test_readiness_planes_remain_independent() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation.py').read_text()
    for label in (
        'Provider Readiness',
        'Inventory Readiness',
        'Metrics Readiness',
        'Webhook Readiness',
    ):
        assert label in presentation
