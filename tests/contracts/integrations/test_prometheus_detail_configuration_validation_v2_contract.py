from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'app/templates/prometheus/partials/_detail_configuration.html'
VALIDATION = ROOT / 'app/templates/prometheus/partials/_detail_validation_content.html'
DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
PROMQL_REGISTRY = ROOT / 'app/templates/prometheus/partials/_capability_registry.html'
PROMETHEUS_ROUTES = ROOT / 'app/prometheus/routes.py'


def test_configuration_uses_shared_read_only_contract_and_edit_route():
    text = CONFIG.read_text()
    shared = (ROOT / 'app/templates/integrations/components/_provider_configuration_contract.html').read_text()
    routes = PROMETHEUS_ROUTES.read_text()
    assert 'provider_configuration_contract.render(' in text
    assert 'data-kaori-provider-configuration-contract' in shared
    assert 'Configure Connection' in shared
    assert 'url_for("prometheus.edit_instance"' in text
    assert "@prometheus_bp.route('/instances/<int:instance_id>/edit'" in routes
    assert '<form' not in text


def test_configuration_keeps_metrics_source_identity_and_prometheus_api_contract_explicit():
    text = CONFIG.read_text()
    assert 'Prometheus API Endpoint' in text
    assert 'Thanos Query API Endpoint' in text
    assert "metrics_source_label = 'Thanos Query' if instance.source_type == 'thanos' else 'Prometheus'" in text
    assert 'provider-neutral Prometheus HTTP API and PromQL capabilities' in text


def test_validation_uses_kubernetes_style_capability_readiness_before_full_width_registry():
    text = VALIDATION.read_text()
    registry = PROMQL_REGISTRY.read_text()
    assert 'Prometheus Full Validation' in text
    assert 'Prometheus Provider Readiness' in text
    assert 'integrations/components/_capability_readiness.html' in text
    assert 'capability_readiness.render(' in text
    assert 'include "prometheus/partials/_capability_registry.html"' in text
    assert 'Capability Registry' in registry
    assert 'data-kaori-provider-capability-matrix' in text
    assert 'Validation Decision' not in text
    assert 'lg:sticky lg:top-4' not in text


def test_promql_registry_is_full_width_and_uses_server_backed_kaori_loading():
    text = PROMQL_REGISTRY.read_text()
    routes = PROMETHEUS_ROUTES.read_text()
    assert 'overflow-hidden' in text
    assert 'table-fixed' in text
    assert '<col class="w-[38%]">' in text
    assert "table_ui.table_classes('min-w-[820px]')" not in text
    assert 'overflow-x-auto' not in text
    assert 'components/pagination.html' in text
    assert 'components/loading_bar.html' in text
    assert 'prometheus-capability-loading' in text
    assert 'hx-indicator="#{{ loading_id }}"' in text
    assert 'data-kaori-server-filtered-registry' in text
    assert 'data-kaori-auto-submit' in text
    assert 'pagination.allowed_per_page' in text
    assert 'Showing <span' in text
    assert 'x-model' not in text
    assert 'filteredRows()' not in text
    assert "@prometheus_bp.get('/instances/<int:instance_id>/validation/capabilities')" in routes
    assert 'def instance_capability_registry' in routes


def test_validation_filters_are_htmx_backed_and_buttonless():
    text = PROMQL_REGISTRY.read_text()
    assert 'Search Capability' in text
    assert 'All Requirements' in text
    assert 'All Statuses' in text
    assert 'Apply Filters' not in text
    assert 'Reset Filters' not in text
    assert 'integration_ui.filter_region_classes()' in text
    assert 'integration_ui.search_classes()' in text
    assert 'integration_ui.control_classes()' in text
    assert 'hx-trigger="input changed delay:300ms' in text
    assert 'hx-get="{{ url_for(registry_endpoint, instance_id=instance.id) }}"' in text


def test_prometheus_detail_alpine_shell_is_not_corrupted():
    text = DETAIL.read_text()
    assert 'integrationWorkspaceTabs(' in text
    assert 'x-on:popstate.window="syncTab()"' in text
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in text


def test_promql_view_more_matches_kubernetes_capability_evidence_concept():
    registry = PROMQL_REGISTRY.read_text()
    shared = (ROOT / 'app/templates/integrations/components/_provider_capability_detail.html').read_text()
    actions = (ROOT / 'app/templates/integrations/components/_record_actions.html').read_text()
    assert 'provider_capability_detail.content(' in registry
    assert 'record_actions.view_more(' in registry
    assert 'Prometheus Core Capability Evidence' in registry
    for token in (
        'Capability Contract',
        'Validation Evidence',
        'Success Criteria',
        'Operational Impact',
        'Recommended Action',
        'Technical Verification',
        'Evidence Boundary',
    ):
        assert token in shared
    assert '{{ table_ui.action_classes() }}' in actions
    assert 'data-lucide="chevron-right"' in actions
    assert 'panel-top-open' not in actions
