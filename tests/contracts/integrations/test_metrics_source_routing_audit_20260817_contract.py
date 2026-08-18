from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_metrics_source_is_provider_neutral_first_class_integration() -> None:
    model = read('app/models/metrics_source.py')
    integration_module = read('app/integrations/observability/metrics_source/__init__.py')
    providers = read('app/integrations/observability/metrics_source/providers.py')
    catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    routes = read('app/integrations/routes.py')
    workspace = read('app/templates/integrations/observability/metrics_source/frontpage.html')

    assert "__tablename__ = 'metrics_sources'" in model
    assert 'creator=_metrics_source_identity' not in model
    service = read('app/integrations/observability/metrics_source/application/service.py')
    assert "integration_type='metrics_source'" in service
    assert service.count('.provider_key = provider.key') >= 3
    assert service.count('.adapter_key = provider.adapter_key') >= 3
    assert 'provider_key: AssociationProxy[str]' in model
    assert 'adapter_key: AssociationProxy[str]' in model
    assert 'query_language: Mapped[str]' in model
    assert 'source_type:' not in model
    assert "integration_type='metrics_source'" in integration_module
    assert "integration_provider_document('metrics_source')" in providers
    assert 'provider_kinds:' in catalog
    assert '- key: prometheus' in catalog
    assert '- key: thanos' in catalog
    assert 'adapter_key: prometheus_http' in catalog
    assert "@integrations_bp.get('/observability/metrics-sources/new')" in routes
    assert "@integrations_bp.route('/observability/metrics-sources/<string:provider_key>/new'" in routes
    assert 'select_metrics_source_provider' in routes
    assert 'register_metrics_source(provider_key: str)' in routes
    assert '/observability/metrics/prometheus/new' not in routes
    assert '/observability/metrics/thanos/new' not in routes
    assert 'Metrics Sources' in workspace
    assert 'integrations.select_metrics_source_provider' in workspace


def test_metrics_source_adapter_and_binding_profiles_are_extension_points() -> None:
    adapter = read('app/integrations/observability/metrics_source/adapter.py')
    backend_registry = read('app/integrations/observability/metrics_source/backend_registry.py')
    profiles = read('app/integrations/observability/metrics_source/binding_profiles.py')
    validation = read('app/integrations/observability/metrics_source/binding_validation.py')
    registry = read('app/integrations/observability/metrics_source/binding_validators/registry.py')
    catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    runtime = read('app/integrations/observability/metrics_source/adapters/prometheus_http/runtime.py')
    providers = read('app/integrations/observability/metrics_source/providers.py')
    compatibility = read('app/integrations/compatibility.py')

    assert 'class MetricsBackendAdapter' in backend_registry
    assert 'def register_metrics_backend(' in backend_registry
    assert 'def metrics_backend_for(' in backend_registry
    assert 'from app.integrations.observability.metrics_source.backend_registry import (' in adapter
    assert 'MetricsSourceError' in backend_registry
    assert "'validation.session.build'" in adapter
    assert "'client.build'" not in adapter
    assert "key = 'prometheus_http'" in adapter
    assert 'adapter_key: str' in profiles
    assert 'expression: str' in profiles
    assert 'signal_key: str' in profiles
    assert 'get_binding_validation_profile(instance.adapter_key, binding.asset_type)' in validation
    assert 'get_binding_validator(instance.adapter_key, binding.asset_type)' in validation
    assert 'def get_binding_validator(adapter_key: str, asset_type: str)' in registry
    assert '- adapter_key: prometheus_http' in catalog
    assert '- expression: count(kube_node_info)' in catalog
    assert 'validation_query:' not in catalog
    assert 'endpoint_capabilities: tuple[str, ...]' in providers
    assert 'endpoint_capabilities=string_tuple(' in providers
    assert 'capabilities=definition.endpoint_capabilities' in runtime
    assert 'definition.key ==' not in runtime
    assert "get_profile('prometheus'" not in runtime
    assert 'get_profile_by_key(config.compatibility_profile_override)' in runtime
    assert 'def get_profile_by_key(' in compatibility


def test_metrics_bindings_have_horizon_and_weight_routing_contract() -> None:
    model = read('app/models/integration.py')
    lifecycle = read('app/integrations/lifecycle.py')
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    registry = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    management = read('app/integrations/observability/metrics_source/binding_management.py')
    resolver = read('app/integrations/observability/metrics_source/application/resolver.py')

    assert 'routing_policy: Mapped[dict | None]' in model
    assert 'routing_policy: dict | None = None' in lifecycle
    assert 'Query Horizon' in modal
    assert 'Routing Weight' in modal
    assert 'Recent Preferred' in modal
    assert 'Historical Preferred' in modal
    assert 'row.query_horizon|title' in registry
    assert 'row.routing_weight' in registry
    assert "requested_horizon = str(routing_policy['query_horizon'])" in management
    assert 'exclude_binding_id=binding.id' in management
    assert 'routing_rank(routing_policy, requested_horizon=query_horizon)' in resolver
    score = resolver.split('score=(', 1)[1].split('binding.id,', 1)[0]
    assert score.index('operational_rank') < score.index('horizon_rank')
    assert score.index('horizon_rank') < score.index('_ROLE_ORDER.get')
    assert score.index('_ROLE_ORDER.get') < score.index('weight_rank')
    assert 'weight_rank' in score


def test_metrics_query_horizon_is_selected_from_actual_query_time_boundary() -> None:
    routing = read('app/integrations/observability/metrics_source/routing.py')
    consumer = read('app/integrations/observability/metrics_source/application/consumer.py')
    config = read('app/config/default.py')
    env_example = read('.env.example')

    assert 'DEFAULT_RECENT_WINDOW_HOURS = 24' in routing
    assert "return 'historical' if timestamp < cutoff else 'recent'" in routing
    assert "return 'historical' if start_timestamp < cutoff else 'recent'" in routing
    assert "query_horizon='recent'" in consumer
    assert 'query_horizon=query_horizon_for_timestamp(timestamp)' in consumer
    assert 'query_horizon=query_horizon_for_range(start, end)' in consumer
    assert "METRICS_RECENT_WINDOW_HOURS = _bounded_env_int('METRICS_RECENT_WINDOW_HOURS', 24, 1, 8760)" in config
    assert 'METRICS_RECENT_WINDOW_HOURS=24' in env_example


def test_metrics_source_workspace_filters_by_provider_key_not_product_category() -> None:
    service = read('app/integrations/service.py')
    registry = read('app/templates/integrations/observability/metrics_source/partials/_instance_inventory.html')
    rows = read('app/templates/integrations/observability/metrics_source/partials/_inventory_content.html')
    domain = read('app/templates/integrations/partials/_domain_workspace.html')

    assert "'provider_key': provider.key" in service
    assert "'provider_options': provider_options()" in service
    assert "'provider_key', selected_provider_key, 'Metrics Provider'" in registry
    assert 'row.provider_label' in rows
    assert 'row.adapter_key' in rows
    assert 'row.query_language' in rows
    assert 'row.routing_label' in domain
    assert 'Observability Routing' in domain
    assert 'Alertmanager remains an alert source' in domain


def test_generalization_migration_removes_product_category_from_runtime_schema() -> None:
    migration = read('migrations/versions/20260817_metrics_source_generalization.py')
    runtime = read('app/integrations/observability/metrics_source/adapter.py')
    lifecycle = read('app/integrations/lifecycle.py')

    assert "revision = '20260817_metrics_source_v2'" in migration
    assert len('20260817_metrics_source_v2') <= 32
    assert "op.rename_table('prometheus_instances', 'metrics_sources')" in migration
    assert "('prometheus_instances_pkey', 'metrics_sources_pkey')" in migration
    assert "('fk_prometheus_instances_integration_instance', 'fk_metrics_sources_integration_instance')" in migration
    assert "('uq_prometheus_instances_integration_instance', 'uq_metrics_sources_integration_instance')" in migration
    assert "sequence_old = 'prometheus_instances_id_seq'" in migration
    assert "sequence_new = 'metrics_sources_id_seq'" in migration
    assert "'source_type'," in migration
    assert "new_column_name='provider_key'" in migration
    assert "sa.Column('adapter_key'" in migration
    assert "sa.Column('query_language'" in migration
    assert "provider_type = 'metrics_source'" in migration
    assert "'metrics_provider_key'" in migration
    assert "'metrics_adapter_key'" in migration
    assert "'metrics_query_language'" in migration
    assert "integration_type = 'metrics_source'" in runtime
    assert 'canonical.provider_key = provider_key' in lifecycle
    assert 'canonical.adapter_key = adapter_key' in lifecycle
    assert "metadata['metrics_query_language'] = getattr(provider_record, 'query_language', None)" in lifecycle
