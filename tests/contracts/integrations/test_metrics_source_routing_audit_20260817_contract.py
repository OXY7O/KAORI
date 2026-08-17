from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_metrics_sources_are_explicit_prometheus_and_thanos_types() -> None:
    model = read('app/models/prometheus.py')
    form = read('app/prometheus/forms.py')
    service = read('app/prometheus/service.py')
    workspace = read('app/templates/integrations/prometheus.html')
    registration = read('app/templates/prometheus/instance_form.html')
    migration = read('migrations/versions/20260817_metrics_routing.py')
    routes = read('app/integrations/routes.py')

    assert 'source_type: Mapped[str] = mapped_column(String(20)' in model
    assert "AnyOf(('prometheus', 'thanos'))" in form
    assert "source_type = str(form.source_type.data or 'prometheus')" in service
    assert "instance.version_detection_mode = 'manual' if source_type == 'thanos' else 'automatic'" in service
    assert 'Metrics Sources' in workspace
    assert 'integrations.register_prometheus_metrics_source' in workspace
    assert 'integrations.register_thanos_metrics_source' in workspace
    assert 'Register Thanos Query' in workspace
    assert 'Metrics Source Contract' in registration
    assert 'Manual — Prometheus-Compatible Gateway' not in registration
    assert 'integrations.register_prometheus_metrics_source' in registration
    assert 'integrations.register_thanos_metrics_source' in registration
    assert "UPDATE prometheus_instances SET source_type = 'thanos'" in migration
    assert "'/observability/metrics/prometheus/new'" in routes
    assert "'/observability/metrics/thanos/new'" in routes
    assert "source_type_override='prometheus'" in routes
    assert "source_type_override='thanos'" in routes


def test_metrics_bindings_have_horizon_and_weight_routing_contract() -> None:
    model = read('app/models/integration.py')
    lifecycle = read('app/integrations/lifecycle.py')
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    registry = read('app/templates/prometheus/partials/_binding_registry.html')
    management = read('app/integrations/prometheus/binding_management.py')
    resolver = read('app/prometheus/resolver.py')

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
    routing = read('app/integrations/prometheus/routing.py')
    consumer = read('app/prometheus/consumer.py')
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


def test_observability_metrics_workspace_exposes_source_type_filter_and_routing_evidence() -> None:
    service = read('app/integrations/service.py')
    registry = read('app/templates/integrations/prometheus/partials/_instance_inventory.html')
    rows = read('app/templates/integrations/prometheus/partials/_inventory_content.html')
    domain = read('app/templates/integrations/partials/_domain_workspace.html')

    assert "source_type = instance.source_type or 'prometheus'" in service
    assert "'source_type': source_type" in service
    assert "'prometheus': sum(1 for row in rows if row['source_type'] == 'prometheus')" in service
    assert "'thanos': sum(1 for row in rows if row['source_type'] == 'thanos')" in service
    assert "'source_type', selected_source_type, 'Source Type'" in registry
    assert 'row.source_type_label' in rows
    assert 'row.routing_label' in domain
    assert 'Observability Routing' in domain
    assert 'Alertmanager remains an alert source' in domain


def test_observability_domain_registry_distinguishes_prometheus_and_thanos_sources() -> None:
    domain_service = read('app/integrations/domain_service.py')
    migration = read('migrations/versions/20260817_metrics_routing.py')
    runtime = read('app/integrations/prometheus/adapter.py')

    assert "return 'Thanos Query', 'prometheus:thanos'" in domain_service
    assert "return 'Prometheus', 'prometheus:prometheus'" in domain_service
    assert "row['provider_filter_key'] == provider_type" in domain_service
    assert "row['source_provider_filter_key'] == provider" in domain_service
    assert "jsonb_build_object('metrics_source_type', pi.source_type)" in migration
    assert "'metrics_source_type': instance.source_type or 'prometheus'" in runtime
