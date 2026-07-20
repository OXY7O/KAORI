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
HISTORY = Path('app/templates/prometheus/partials/_runtime_history.html')
BINDINGS = Path('app/templates/prometheus/instances.html')
CONFIG = Path('app/templates/prometheus/config.html')
READINESS = Path('app/templates/prometheus/partials/_analytics_readiness.html')
ROUTES = Path('app/integrations/routes.py')
LEGACY_REGISTRY = Path('app/templates/integrations/prometheus/partials/_inventory_card.html')


def test_prometheus_landing_uses_shared_kaori_workspace_components() -> None:
    source = LANDING.read_text(encoding='utf-8')
    required = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        "page_hero.intro('activity', 'Operational Integration', 'chart-no-axes-combined')",
        'page_hero.aside_classes()',
        'page_hero.context_panel_classes()',
        'Prometheus Integration Overview',
        'Integration Contract',
        'Usage Resolution',
        'Authority Boundary',
        'Connection Readiness and Bindings',
        'page_hero.context_panel_metrics_classes()',
        "integrations/prometheus/partials/_instance_inventory.html",
    )
    missing = [fragment for fragment in required if fragment not in source]
    assert not missing, f'Prometheus landing workspace is incomplete: {missing}'
    assert 'font-bold' not in source


def test_prometheus_registry_uses_htmx_filters_and_standard_pagination() -> None:
    wrapper = REGISTRY.read_text(encoding='utf-8')
    content = REGISTRY_CONTENT.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')

    required_wrapper = (
        'Prometheus Connection Registry',
        'hx-target="#prometheus-inventory-content"',
        'hx-trigger="change from:select, keyup changed delay:500ms',
        'id="prometheus-inventory-loading"',
        'animate-pulse rounded-full bg-kaori-primary',
        'Search Connection',
        'Compatibility',
    )
    missing = [fragment for fragment in required_wrapper if fragment not in wrapper]
    assert not missing, f'Prometheus registry filters are incomplete: {missing}'
    assert '>Apply<' not in wrapper
    assert 'Register Connection' not in wrapper
    assert 'Instances & Bindings' not in wrapper

    required_content = (
        'font-sans text-sm font-normal text-content-secondary',
        'table_label.metadata_label',
        'status_badge(row.compatibility)',
        'status_badge(row.readiness)',
        'Showing <strong class="font-semibold text-content-primary"',
        'aria-label="Connections per page"',
        'hx-push-url="true"',
        'pagination_ui.numeric_pages(pagination.page, pagination.total_pages)',
        "url_for('prometheus.instance_detail', instance_id=row.instance_id)",
    )
    missing = [fragment for fragment in required_content if fragment not in content]
    assert not missing, f'Prometheus registry content is incomplete: {missing}'
    assert "render_template('integrations/prometheus/partials/_inventory_content.html'" in routes


def test_prometheus_instance_detail_uses_standard_domain_tabs_and_summaries() -> None:
    source = DETAIL.read_text(encoding='utf-8')
    configuration = CONFIG_DETAIL.read_text(encoding='utf-8')
    validation = VALIDATION_DETAIL.read_text(encoding='utf-8')
    runtime = RUNTIME_DETAIL.read_text(encoding='utf-8')
    scope = SCOPE_DETAIL.read_text(encoding='utf-8')

    required_shell = (
        'role="tablist"',
        "('configuration', 'Configuration', 'settings-2'",
        "('validation', 'Validation & Capabilities', 'scan-search'",
        "('runtime', 'Runtime & History', 'activity'",
        "('scope', 'Scope & Resolution', 'route'",
        "prometheus/partials/_detail_configuration.html",
        "prometheus/partials/_detail_validation.html",
        "prometheus/partials/_detail_runtime.html",
        "prometheus/partials/_detail_scope.html",
    )
    missing = [fragment for fragment in required_shell if fragment not in source]
    assert not missing, f'Prometheus manage shell is incomplete: {missing}'

    assert configuration.count('workspace_summary_card.render') == 3
    assert 'info_flow.render' in configuration
    assert "'Configuration Flow'" in configuration
    assert validation.count('workspace_summary_card.render') == 3
    assert runtime.count('workspace_summary_card.render') == 3
    assert 'Instance Lifecycle &amp; Deletion' in scope


def test_prometheus_runtime_history_and_binding_workspace_follow_kaori_violet() -> None:
    runtime = RUNTIME.read_text(encoding='utf-8')
    history = HISTORY.read_text(encoding='utf-8')
    bindings = BINDINGS.read_text(encoding='utf-8')

    required_runtime = (
        'Runtime Health &amp; Diagnostics',
        'health_interpretation.render',
        'Diagnostic Pipeline',
        'table_label.status_label',
        'table_label.metadata_label',
        'No action required.',
    )
    missing = [fragment for fragment in required_runtime if fragment not in runtime]
    assert not missing, f'Prometheus runtime workspace is incomplete: {missing}'

    required_history = (
        '100-Record Retention',
        'Showing <span class="font-semibold text-content-primary"',
        'aria-label="Runtime observations per page"',
        'pagination_ui.numeric_pages(runtime_history.pagination.page, runtime_history.pagination.total_pages)',
        'Run Refresh Runtime or wait for scheduled monitoring.',
    )
    missing = [fragment for fragment in required_history if fragment not in history]
    assert not missing, f'Prometheus runtime history is incomplete: {missing}'

    required_bindings = (
        'page_hero.shell_classes()',
        'Prometheus Instances & Bindings',
        'How Bindings Participate in Source Resolution',
        'xl:grid-cols-12',
        'xl:col-span-8',
        'xl:sticky xl:top-5 xl:col-span-4',
        '<h3 class="text-base font-semibold text-content-primary">Create Binding</h3>',
        'Pre-save Validation',
        'data-prometheus-delete-button',
        'Manage Scope &amp; Lifecycle',
        'Create Binding',
    )
    missing = [fragment for fragment in required_bindings if fragment not in bindings]
    assert not missing, f'Prometheus binding workspace is incomplete: {missing}'
    assert "{% include 'prometheus/partials/_delete_confirmation_modal.html' %}" not in bindings.split('{% block dashboard_content %}', 1)[0]


def test_prometheus_cluster_configuration_and_readiness_are_standardized() -> None:
    config = CONFIG.read_text(encoding='utf-8')
    readiness = READINESS.read_text(encoding='utf-8')
    required = (
        'page_hero.shell_classes()',
        'role="tablist"',
        'Configuration',
        'Validation & Analytics',
        'Runtime & History',
        'workspace_summary_card.render',
        'info_flow.render',
        'Test Connection',
        'Run Full Validation',
    )
    missing = [fragment for fragment in required if fragment not in config]
    assert not missing, f'Prometheus cluster configuration is incomplete: {missing}'
    assert 'Analytics Readiness' in readiness
    assert 'Operational Domain Readiness' in readiness
    assert 'rounded-full' not in readiness


def test_obsolete_prometheus_registry_partial_is_removed() -> None:
    assert not LEGACY_REGISTRY.exists(), 'Unused legacy Prometheus inventory card must be removed.'
