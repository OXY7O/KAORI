from pathlib import Path

LANDING = Path('app/templates/integrations/prometheus.html')
REGISTRY = Path('app/templates/integrations/prometheus/partials/_instance_inventory.html')
REGISTRY_CONTENT = Path('app/templates/integrations/prometheus/partials/_inventory_content.html')
FORM = Path('app/templates/prometheus/instance_form.html')
DETAIL = Path('app/templates/prometheus/instance_detail.html')
CONFIG_DETAIL = Path('app/templates/prometheus/partials/_detail_configuration.html')
VALIDATION_DETAIL = Path('app/templates/prometheus/partials/_detail_validation.html')
RUNTIME_DETAIL = Path('app/templates/prometheus/partials/_detail_runtime.html')
SCOPE_DETAIL = Path('app/templates/prometheus/partials/_detail_scope.html')
RUNTIME = Path('app/templates/prometheus/partials/_runtime_panel.html')
HISTORY = Path('app/templates/integrations/partials/_runtime_history.html')
READINESS = Path('app/templates/prometheus/partials/_analytics_readiness.html')
ROUTES = Path('app/integrations/routes.py')
RETIRED_REGISTRY = Path('app/templates/integrations/prometheus/partials/_inventory_card.html')


def test_prometheus_landing_uses_shared_kaori_workspace_components() -> None:
    source = LANDING.read_text(encoding='utf-8')
    required = (
        'page_hero.shell_classes()',
        'Prometheus Integration Overview',
        'Integration Contract',
        'Usage Resolution',
        'Authority Boundary',
        'Connection Readiness and Bindings',
        "integrations/prometheus/partials/_instance_inventory.html",
    )
    missing = [fragment for fragment in required if fragment not in source]
    assert not missing, f'Prometheus landing workspace is incomplete: {missing}'


def test_prometheus_registry_uses_htmx_filters_and_standard_pagination() -> None:
    wrapper = REGISTRY.read_text(encoding='utf-8')
    content = REGISTRY_CONTENT.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')
    for fragment in (
        'Prometheus Connection Registry',
        'hx-target="#prometheus-inventory-content"',
        'Search Connection',
        'Compatibility',
    ):
        assert fragment in wrapper
    for fragment in (
        'status_badge(row.compatibility)',
        'status_badge(row.readiness)',
        'aria-label="Connections per page"',
        'pagination_ui.numeric_pages(pagination.page, pagination.total_pages)',
        "url_for('prometheus.instance_detail', instance_id=row.instance_id)",
    ):
        assert fragment in content
    assert "render_template('integrations/prometheus/partials/_inventory_content.html'" in routes


def test_prometheus_instance_detail_owns_configuration_validation_runtime_and_scope() -> None:
    source = DETAIL.read_text(encoding='utf-8')
    configuration = CONFIG_DETAIL.read_text(encoding='utf-8')
    validation = VALIDATION_DETAIL.read_text(encoding='utf-8')
    runtime = RUNTIME_DETAIL.read_text(encoding='utf-8')
    scope = SCOPE_DETAIL.read_text(encoding='utf-8')
    for fragment in (
        "('configuration', 'Configuration', 'settings-2'",
        "('validation', 'Validation & Capabilities', 'scan-search'",
        "('runtime', 'Runtime & History', 'activity'",
        "('scope', 'Scope & Resolution', 'route'",
    ):
        assert fragment in source
    assert configuration.count('workspace_summary_card.render') == 3
    assert validation.count('workspace_summary_card.render') == 3
    assert runtime.count('workspace_summary_card.render') == 3
    assert "integrations/partials/_runtime_history.html" in runtime
    assert 'Instance Lifecycle &amp; Deletion' in scope


def test_prometheus_runtime_history_uses_the_shared_component_directly() -> None:
    runtime_panel = RUNTIME.read_text(encoding='utf-8')
    history = HISTORY.read_text(encoding='utf-8') + RUNTIME_DETAIL.read_text(encoding='utf-8')
    for fragment in (
        'Runtime Health &amp; Diagnostics',
        'Diagnostic Pipeline',
        'No action required.',
    ):
        assert fragment in runtime_panel
    for fragment in (
        'Recent Runtime Observations',
        'Manage Lifecycle',
        'aria-label="Runtime observations per page"',
        'pagination_ui.numeric_pages(runtime_history.pagination.page, runtime_history.pagination.total_pages)',
        'prometheus-history-loading',
    ):
        assert fragment in history
    assert not Path('app/templates/prometheus/partials/_runtime_history.html').exists()


def test_prometheus_readiness_and_retired_templates_are_canonical() -> None:
    readiness = READINESS.read_text(encoding='utf-8')
    assert 'Analytics Readiness' in readiness
    assert 'Operational Domain Readiness' in readiness
    assert 'rounded-full' not in readiness
    assert not RETIRED_REGISTRY.exists()
    assert not Path('app/templates/prometheus/config.html').exists()
    assert not Path('app/templates/prometheus/instances.html').exists()
