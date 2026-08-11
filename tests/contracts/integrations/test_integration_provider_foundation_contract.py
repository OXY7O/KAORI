from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_registry_owns_domain_capability_and_provider_extension_metadata() -> None:
    registry = read('app/integrations/registry.py')
    taxonomy = read('app/integrations/taxonomy.py')

    for field in (
        'domain_key: str',
        'capability_key: str',
        'workspace_endpoint: str',
        'navigation_endpoint_prefixes: tuple[str, ...]',
        'canonical_record_loader: CanonicalRecordLoader',
        'detail_url_builder: DetailUrlBuilder | None',
        'failure_recorder: FailureRecorder | None',
    ):
        assert field in registry

    for domain in ("key='orchestration'", "key='observability'", "key='storage'"):
        assert domain in taxonomy
    for capability in (
        "key='cluster_orchestration'",
        "key='metrics'",
        "key='alerting'",
        "key='object_storage'",
        "key='file_storage'",
        "key='block_storage'",
    ):
        assert capability in taxonomy


def test_builtin_provider_registration_uses_canonical_taxonomy() -> None:
    registrations = {
        'app/integrations/kubernetes/__init__.py': (
            "domain_key='orchestration'",
            "capability_key='cluster_orchestration'",
        ),
        'app/integrations/prometheus/__init__.py': (
            "domain_key='observability'",
            "capability_key='metrics'",
        ),
        'app/integrations/alertmanager/__init__.py': (
            "domain_key='observability'",
            "capability_key='alerting'",
        ),
        'app/integrations/minio/__init__.py': (
            "domain_key='storage'",
            "capability_key='object_storage'",
        ),
    }
    for path, expected in registrations.items():
        source = read(path)
        assert expected[0] in source
        assert expected[1] in source
        assert 'canonical_record_loader=canonical_model_loader(' in source
        assert 'workspace_endpoint=' in source


def test_binding_service_is_asset_centric_and_keeps_kubernetes_wrapper() -> None:
    binding_service = read('app/integrations/binding_service.py')
    prometheus_adapter = read('app/integrations/prometheus/adapter.py')
    prometheus_binding = read('app/integrations/prometheus/binding_management.py')

    assert 'def create_source_binding(' in binding_service
    assert 'asset_type: str' in binding_service
    assert 'asset_key: str' in binding_service
    assert 'scope_type=normalized_asset_type' in binding_service
    assert 'scope_key=normalized_asset_key' in binding_service
    assert "if provider not in {'prometheus', 'alertmanager'}" not in binding_service
    assert 'def create_cluster_source_binding(' in binding_service
    assert "asset_type='kubernetes_cluster'" in binding_service

    assert 'spec=SourceBindingSpec(' in prometheus_adapter
    assert "asset_type=str(kwargs.get('scope_type') or '')" in prometheus_adapter
    assert "asset_key=str(kwargs.get('scope_key') or '')" in prometheus_adapter
    assert 'spec: SourceBindingSpec' in prometheus_binding
    assert 'asset_type=normalized_scope_type' in prometheus_binding
    assert 'asset_key=normalized_scope_key' in prometheus_binding


def test_provider_record_resolution_no_longer_branches_on_provider_names() -> None:
    resolver = read('app/integrations/resolver.py')
    provider_record = resolver.split('def provider_record', 1)[1]

    assert 'get_integration(instance.provider_type)' in provider_record
    assert 'get_record_for_canonical(instance.id)' in provider_record
    assert "instance.provider_type == 'prometheus'" not in provider_record
    assert "instance.provider_type == 'alertmanager'" not in provider_record
    assert "instance.provider_type == 'kubernetes'" not in provider_record
    assert "instance.provider_type == 'minio'" not in provider_record


def test_validation_worker_dispatches_full_validation_through_registry() -> None:
    tasks = read('app/integrations/validation/tasks.py')
    full_validation = tasks.split('def validate_integration_instance', 1)[1].split('def _as_result_payload', 1)[0]

    assert 'module = get_integration(provider_type)' in full_validation
    assert 'instance = module.get_instance(instance_id)' in full_validation
    assert 'runtime_refresh.refresh_and_record(' in full_validation
    assert "if 'binding.validate' in module.operations" in full_validation
    assert '_refresh_provider_bindings(' in full_validation
    assert "provider_type == 'prometheus'" not in full_validation
    assert "provider_type == 'alertmanager'" not in full_validation
    assert "provider_type == 'kubernetes'" not in full_validation
    assert "provider_type == 'minio'" not in full_validation


def test_prometheus_binding_validation_is_asset_profile_driven() -> None:
    profiles = read('app/integrations/prometheus/binding_profiles.py')
    validation = read('app/integrations/prometheus/binding_validation.py')

    assert 'class BindingValidationProfile' in profiles
    assert 'def register_binding_validation_profile(' in profiles
    assert 'asset_type=KUBERNETES_CLUSTER_SCOPE' in profiles
    assert 'get_binding_validation_profile(binding.asset_type)' in validation
    assert "('kube_node_info', 'Kubernetes node identity')" not in validation
    assert 'No Prometheus binding validation profile is registered for asset type' in validation


def test_overview_catalog_is_registry_driven_and_storage_is_domain_not_fake_provider() -> None:
    service = read('app/integrations/service.py')
    overview = read('app/templates/integrations/overview.html')

    catalog = service.split('def _catalog', 1)[1].split('def _ordered_status_options', 1)[0]
    coverage = service.split('def _coverage(', 1)[1].split('def _coverage_stats', 1)[0]

    assert 'for module in registry.all()' in catalog
    assert "'category': module.domain.label" in catalog
    assert "'capability': module.capability.label" in catalog
    assert "'workspace_endpoint': module.workspace_endpoint" in catalog
    assert 'S3-compatible Storage' not in catalog
    assert "'name': 'Vault'" not in catalog

    assert 'for domain in ordered_domain_definitions()' in coverage
    assert 'capability_definitions_for_domain(domain.key)' in coverage
    assert 'Compute & Infrastructure' not in coverage

    assert 'href="{{ url_for(item.workspace_endpoint) }}"' in overview
    assert "item.key == 'kubernetes'" not in overview
    assert "item.key == 'prometheus'" not in overview
    assert '{{ item.category }} · {{ item.capability }}' in overview
