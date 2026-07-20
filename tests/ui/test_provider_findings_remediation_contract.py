from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_edit_workspaces_can_test_submitted_connection_settings() -> None:
    prometheus_template = read("app/templates/prometheus/partials/_detail_configuration.html")
    alertmanager_template = read("app/templates/alertmanager/partials/_detail_configuration.html")
    kubernetes_template = read("app/templates/cluster/partials/_form.html")
    prometheus_routes = read("app/prometheus/routes.py")
    alertmanager_routes = read("app/alertmanager/routes.py")
    kubernetes_routes = read("app/cluster/routes.py")

    assert "prometheus.test_instance_configuration" in prometheus_template
    assert "alertmanager.test_instance_configuration" in alertmanager_template
    assert "cluster.test_edit_cluster_connection" in kubernetes_template
    assert "Test Connection" in prometheus_template
    assert "Test Connection" in alertmanager_template
    assert "Test Connection" in kubernetes_template
    assert "@prometheus_bp.post('/instances/<int:instance_id>/test-configuration')" in prometheus_routes
    assert "@alertmanager_bp.post('/instances/<int:instance_id>/test-configuration')" in alertmanager_routes
    assert "@cluster_bp.post('/<string:cluster_id>/edit/test-connection')" in kubernetes_routes
    for routes in (prometheus_routes, alertmanager_routes, kubernetes_routes):
        assert "draft_update" in routes
        assert "queue_feedback=False" in routes


def test_edit_connection_tests_reuse_saved_secret_without_persistence() -> None:
    prometheus = read("app/prometheus/service.py")
    alertmanager = read("app/alertmanager/service.py")
    assert "existing_instance: PrometheusInstance | None = None" in prometheus
    assert "password = existing_instance.password" in prometheus
    assert "bearer_token = existing_instance.bearer_token" in prometheus
    assert "existing_instance: AlertmanagerInstance | None = None" in alertmanager
    assert "password = existing_instance.password" in alertmanager
    assert "bearer_token = existing_instance.bearer_token" in alertmanager


def test_kubernetes_readiness_exposes_factor_level_degraded_evidence() -> None:
    service = read("app/kubernetes/service.py")
    adapter = read("app/integrations/runtime/kubernetes_adapter.py")
    presentation = read("app/integrations/runtime/presentation.py")
    runtime = read("app/templates/integrations/kubernetes/partials/_runtime_workspace.html")
    capability = read("app/templates/integrations/kubernetes/partials/_capability_workspace.html")
    history = read("app/templates/integrations/partials/_runtime_history.html")
    assert "readiness_reasons" in service
    assert "API compatibility and lifecycle" in adapter
    assert "Version lifecycle" in adapter
    assert "attention_factors" in presentation
    assert "Why This Runtime Requires Attention" in runtime
    assert "Why Readiness Is" in capability
    assert "row.message" in history


def test_kubernetes_operational_flow_uses_shared_flow_component() -> None:
    contract = read("app/templates/integrations/kubernetes/partials/_connection_contract.html")
    assert 'import "components/info_flow.html" as info_flow' in contract
    assert "info_flow.render(" in contract
    assert "Operational Flow" in contract
    assert "Configure Connection" in contract
    assert "Run Full Validation" in contract


def test_filesystem_contract_explains_size_and_available_pairs() -> None:
    contracts = read("app/prometheus/query_profiles/feature_contracts.py")
    audit = read("app/prometheus/query_profiles/audit.py")
    capabilities = read("app/prometheus/capabilities.py")
    for fragment in (
        "/var size",
        "/var available",
        "/ size",
        "/ available",
        "canonical node identity",
        "node_filesystem_size_bytes",
        "node_filesystem_avail_bytes",
    ):
        assert fragment in contracts
    assert "assessment['validation_query'] = '\\n'.join" in audit
    assert capabilities.count("node_filesystem_size_bytes") >= 2
    assert capabilities.count("node_filesystem_avail_bytes") >= 2


def test_kubernetes_registry_action_width_matches_icon_density() -> None:
    registry = read("app/templates/integrations/kubernetes/partials/_registry.html")
    assert "w-full min-w-[1088px] table-fixed" in registry
    assert "w-[208px]" in registry
    assert registry.count("inline-flex h-8 w-8") >= 5
