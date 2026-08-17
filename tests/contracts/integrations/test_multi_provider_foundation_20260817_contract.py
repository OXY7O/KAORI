from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_provider_matrix_separates_domain_capability_provider_and_adapter() -> None:
    taxonomy = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    matrix = read('app/definitions/catalogs/integrations/provider_matrix.yaml')

    for domain in ('key: orchestration', 'key: observability', 'key: storage'):
        assert domain in taxonomy

    for integration_type in (
        'key: container_orchestrator',
        'key: metrics_source',
        'key: alert_source',
        'key: object_storage',
        'key: file_storage',
        'key: block_storage',
    ):
        assert integration_type in matrix

    for provider in (
        'key: kubernetes',
        'key: rancher',
        'key: sangfor_kubernetes_engine',
        'key: prometheus',
        'key: thanos',
        'key: alertmanager',
        'key: minio',
        'key: garage',
        'key: aws_s3',
        'key: azure_blob',
        'key: netapp_ontap',
        'key: hpe_alletra',
    ):
        assert provider in matrix

    assert matrix.count('adapter_key: kubernetes_api') >= 3
    assert matrix.count('adapter_key: prometheus_http') >= 2
    assert matrix.count('adapter_key: s3') >= 3
    assert 'adapter_key: azure_blob' in matrix
    assert 'adapter_key: ontap_rest' in matrix
    assert 'adapter_key: hpe_storage_rest' in matrix


def test_core_identity_and_binding_schema_are_provider_neutral() -> None:
    model = read('app/models/integration.py')
    registry = read('app/integrations/registry.py')
    resolver = read('app/integrations/resolver.py')

    for field in ('integration_type', 'provider_key', 'adapter_key'):
        assert f'{field}: Mapped[str]' in model

    assert 'asset_type: Mapped[str]' in model
    assert 'asset_key: Mapped[str]' in model
    assert 'capability_scope: Mapped[list[str] | None]' in model
    assert 'routing_policy: Mapped[dict | None]' in model

    assert 'IntegrationImplementation' in registry
    assert 'provider_kind(integration_type, provider_key)' in registry
    assert 'registry.get_implementation(self.integration_type, provider_key)' in registry

    provider_record = resolver.split('def provider_record', 1)[1]
    assert 'get_integration(instance.integration_type)' in provider_record
    assert "instance.provider_key == '" not in provider_record
    assert "instance.integration_type == 'prometheus'" not in provider_record
    assert "instance.integration_type == 'minio'" not in provider_record


def test_query_profiles_are_adapter_scoped_not_product_scoped() -> None:
    profiles = read('app/integrations/observability/metrics_source/query_profiles/__init__.py')
    registry = read('app/integrations/observability/metrics_source/query_profiles/registry.py')
    metrics_module = read('app/integrations/observability/metrics_source/__init__.py')

    assert "register_query_profile(adapter_key='prometheus_http'" in profiles
    assert 'def resolve_query_reference(' in registry
    assert 'adapter_key: str' in registry
    assert 'profile_key: str' in registry
    assert "provider_key in ('prometheus', 'thanos')" not in registry

    assert "integration_type='metrics_source'" in metrics_module
    assert 'provider_key=provider_key' in metrics_module
    assert "adapter_key='prometheus_http'" in metrics_module


def test_managed_assets_and_consumers_resolve_without_product_model_branching() -> None:
    managed_assets = read('app/integrations/managed_assets.py')
    source_projection = read('app/integrations/asset_owner_sources.py')

    assert 'managed_asset_owner_identity(' in managed_assets
    assert 'IntegrationInstance.metadata_json' in managed_assets
    assert 'get_integration(identity.integration_type)' in managed_assets
    assert 'provider_kind(identity.integration_type, identity.provider_key)' in managed_assets

    assert "canonical.integration_type != 'metrics_source'" in source_projection
    assert 'canonical.provider_key' in source_projection
    assert "canonical.provider_key == 'prometheus'" not in source_projection
    assert "canonical.provider_key == 'thanos'" not in source_projection
