from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'app/templates/prometheus/partials/_detail_configuration.html'
VALIDATION = ROOT / 'app/templates/prometheus/partials/_detail_validation_content.html'
DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
PROMQL_REGISTRY = ROOT / 'app/templates/prometheus/partials/_capability_registry.html'
PROMETHEUS_ROUTES = ROOT / 'app/prometheus/routes.py'


def test_configuration_uses_shared_side_decision_and_primary_form_workspace():
    text = CONFIG.read_text()
    shared = (ROOT / 'app/templates/integrations/components/_configuration_decision.html').read_text()
    assert 'configuration_decision.side_panel(' in text
    assert 'Prometheus Configuration Decision' in text
    assert 'data-kaori-configuration-decision-side' in shared
    assert 'Controlled Flow' in shared
    assert "xl:grid-cols-[minmax(0,1fr)_25rem]" in text
    assert 'xl:sticky xl:top-4' in shared
    assert 'Test Connection' in text
    assert 'Save Changes' in text


def test_configuration_keeps_endpoint_product_semantics_explicit():
    text = CONFIG.read_text()
    assert "'Thanos Query' if endpoint_product == 'thanos' else 'Prometheus'" in text
    assert 'Prometheus Source Version' in text
    assert 'Detection Mode' in text


def test_validation_uses_kubernetes_style_capability_readiness_before_full_width_registry():
    text = VALIDATION.read_text()
    registry = PROMQL_REGISTRY.read_text()
    assert 'Prometheus Validation & PromQL' in text
    assert 'Prometheus Capability Readiness' in text
    assert "integrations/components/_capability_readiness.html" in text
    assert "capability_readiness.render(" in text
    assert "include 'prometheus/partials/_capability_registry.html'" in text
    assert 'PromQL Capability Registry' in registry
    assert 'data-kaori-provider-capability-matrix' in text
    assert 'Validation Decision' not in text
    assert 'lg:sticky lg:top-4' not in text

def test_promql_registry_is_full_width_and_uses_server_backed_kaori_loading():
    text = PROMQL_REGISTRY.read_text()
    routes = PROMETHEUS_ROUTES.read_text()
    assert 'overflow-hidden' in text
    assert 'table-fixed' in text
    assert '<col class="w-[43%]">' in text
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
    assert 'table_ui.inventory_filter_bar_classes()' in text
    assert 'table_ui.filter_input_classes()' in text
    assert 'table_ui.filter_select_classes()' in text
    assert 'hx-trigger="keyup changed delay:300ms' in text
    assert 'hx-get="{{ url_for(registry_endpoint, instance_id=instance.id) }}"' in text


def test_prometheus_detail_alpine_shell_is_not_corrupted():
    text = DETAIL.read_text()
    assert 'integrationWorkspaceTabs(' in text
    assert "x-on:popstate.window=\"syncTab()\"" in text
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in text


def test_promql_view_more_matches_kubernetes_capability_evidence_concept():
    registry = PROMQL_REGISTRY.read_text()
    shared = (ROOT / 'app/templates/integrations/components/_provider_capability_detail.html').read_text()
    actions = (ROOT / 'app/templates/integrations/components/_record_actions.html').read_text()
    assert "provider_capability_detail.content(" in registry
    assert "record_actions.view_more(" in registry
    assert "'Prometheus Capability Evidence'" in registry
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
