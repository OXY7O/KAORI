from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'app/templates/prometheus/partials/_detail_configuration.html'
VALIDATION = ROOT / 'app/templates/prometheus/partials/_detail_validation_content.html'
DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'


def test_configuration_uses_connection_contract_and_decision_panel():
    text = CONFIG.read_text()
    assert 'Prometheus Connection Contract' in text
    assert 'Configuration Decision' in text
    assert "xl:grid-cols-[minmax(0,1fr)_25rem]" in text
    assert 'Test Connection' in text
    assert 'Save Changes' in text


def test_configuration_keeps_endpoint_product_semantics_explicit():
    text = CONFIG.read_text()
    assert "'Thanos Query' if endpoint_product == 'thanos' else 'Prometheus'" in text
    assert 'Prometheus Source Version' in text
    assert 'Detection Mode' in text


def test_validation_uses_horizontal_decision_before_full_width_registry():
    text = VALIDATION.read_text()
    assert 'Prometheus Validation & PromQL' in text
    assert 'Validation Decision' in text
    assert 'PromQL Capability Registry' in text
    assert text.index('Validation Decision') < text.index('PromQL Capability Registry')
    assert 'data-kaori-prometheus-validation-decision' in text
    assert 'data-kaori-prometheus-validation-scope-modal' in text
    assert 'Review Scope' in text
    assert 'Retention Coverage' in text
    assert 'Operational Domains' in text
    assert 'View More' in text
    assert 'lg:grid-cols-[minmax(0,1fr)_20rem]' not in text
    assert 'lg:sticky lg:top-4' not in text
    assert 'data-kaori-prometheus-validation-details' not in text


def test_promql_registry_is_full_width_and_does_not_force_horizontal_scroll():
    text = VALIDATION.read_text()
    assert 'overflow-hidden' in text
    assert 'table-fixed' in text
    assert '<col class="w-[43%]">' in text
    assert "table_ui.table_classes('min-w-[820px]')" not in text
    assert 'overflow-x-auto' not in text


def test_validation_filters_are_local_and_buttonless():
    text = VALIDATION.read_text()
    assert 'Search Capability' in text
    assert 'All Requirements' in text
    assert 'All Statuses' in text
    assert 'Apply Filters' not in text
    assert 'Reset Filters' not in text


def test_prometheus_detail_alpine_shell_is_not_corrupted():
    text = DETAIL.read_text()
    assert "x-on:popstate.window=\"syncTabFromLocation()\">" in text
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in text
