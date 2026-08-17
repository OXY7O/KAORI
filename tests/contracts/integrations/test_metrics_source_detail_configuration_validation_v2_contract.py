from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'app/templates/integrations/observability/metrics_source/partials/_detail_configuration.html'
VALIDATION = ROOT / 'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
DETAIL = ROOT / 'app/templates/integrations/observability/metrics_source/instance_detail.html'
CAPABILITY_REGISTRY = (
    ROOT / 'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html'
)
METRICS_ROUTES = ROOT / 'app/integrations/observability/metrics_source/application/routes.py'


def test_configuration_uses_shared_read_only_contract_and_edit_route():
    text = CONFIG.read_text()
    shared = (ROOT / 'app/templates/integrations/components/_provider_configuration_contract.html').read_text()
    routes = METRICS_ROUTES.read_text()
    assert 'provider_configuration_contract.render(' in text
    assert 'data-kaori-provider-configuration-contract' in shared
    assert 'Configure Connection' in shared
    assert 'url_for("metrics.edit_instance"' in text
    assert "@metrics_bp.route('/instances/<int:instance_id>/edit'" in routes
    assert '<form' not in text


def test_configuration_keeps_provider_identity_and_metrics_contract_explicit():
    text = CONFIG.read_text()
    assert "metrics_source_label ~ ' Metrics Endpoint'" in text
    assert 'metrics_source_label ~ " Query API"' in text
    assert '{% set metrics_source_label = provider.label %}' in text
    assert 'adapter, query-language, and provider capability contract' in text


def test_validation_uses_kubernetes_style_capability_readiness_before_full_width_registry():
    text = VALIDATION.read_text()
    registry = CAPABILITY_REGISTRY.read_text()
    assert 'Metrics Source Full Validation' in text
    assert 'Metrics Source Provider Readiness' in text
    assert 'integrations/components/_capability_readiness.html' in text
    assert 'capability_readiness.render(' in text
    assert 'include "integrations/observability/metrics_source/partials/_capability_registry.html"' in text
    assert 'Capability Registry' in registry
    assert 'data-kaori-provider-capability-matrix' in text
    assert 'Validation Decision' not in text
    assert 'lg:sticky lg:top-4' not in text


def test_capability_registry_is_full_width_and_uses_server_backed_kaori_loading():
    text = CAPABILITY_REGISTRY.read_text()
    routes = METRICS_ROUTES.read_text()
    assert 'overflow-hidden' in text
    assert 'table-fixed' in text
    assert '<col class="w-[38%]">' in text
    assert "table_ui.table_classes('min-w-[820px]')" not in text
    assert 'overflow-x-auto' not in text
    assert 'components/pagination.html' in text
    assert 'components/loading_bar.html' in text
    assert 'metrics-source-capability-loading' in text
    assert 'hx-indicator="#{{ loading_id }}"' in text
    assert 'data-kaori-server-filtered-registry' in text
    assert 'data-kaori-auto-submit' in text
    assert 'pagination.allowed_per_page' in text
    assert 'Showing <span' in text
    assert 'x-model' not in text
    assert 'filteredRows()' not in text
    assert "@metrics_bp.get('/instances/<int:instance_id>/validation/capabilities')" in routes
    assert 'def instance_capability_registry' in routes


def test_validation_filters_are_htmx_backed_and_buttonless():
    text = CAPABILITY_REGISTRY.read_text()
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


def test_metrics_source_detail_alpine_shell_is_not_corrupted():
    text = DETAIL.read_text()
    assert 'integrationWorkspaceTabs(' in text
    assert 'x-on:popstate.window="syncTab()"' in text
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in text


def test_capability_view_more_matches_kubernetes_capability_evidence_concept():
    registry = CAPABILITY_REGISTRY.read_text()
    shared = (ROOT / 'app/templates/integrations/components/_provider_capability_detail.html').read_text()
    actions = (ROOT / 'app/templates/integrations/components/_record_actions.html').read_text()
    assert 'provider_capability_detail.content(' in registry
    assert 'record_actions.view_more(' in registry
    assert 'Metrics Source Core Capability Evidence' in registry
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
