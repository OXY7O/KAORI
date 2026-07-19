from pathlib import Path


LANDING = Path('app/templates/integrations/prometheus.html')
REGISTRY = Path('app/templates/integrations/prometheus/partials/_instance_inventory.html')
REGISTRY_CONTENT = Path('app/templates/integrations/prometheus/partials/_inventory_content.html')
FORM = Path('app/templates/prometheus/instance_form.html')
DETAIL = Path('app/templates/prometheus/instance_detail.html')
RUNTIME = Path('app/templates/prometheus/partials/_runtime_panel.html')
HISTORY = Path('app/templates/prometheus/partials/_runtime_history.html')
BINDINGS = Path('app/templates/prometheus/instances.html')
CONFIG = Path('app/templates/prometheus/config.html')
READINESS = Path('app/templates/prometheus/partials/_analytics_readiness.html')
ROUTES = Path('app/integrations/routes.py')
LEGACY_REGISTRY = Path('app/templates/integrations/prometheus/partials/_inventory_card.html')


def test_prometheus_landing_matches_alertmanager_workspace_concept() -> None:
    source = LANDING.read_text(encoding='utf-8')
    required = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        "page_hero.intro('activity', 'Operational Integration', 'chart-no-axes-combined')",
        'page_hero.aside_classes()',
        'flex h-full min-h-[12rem] flex-col justify-between rounded-xl',
        'Prometheus Integration Overview',
        'Integration Contract',
        'Usage Resolution',
        'Authority Boundary',
        "url_for('prometheus.instances')",
        'Instances & Bindings',
        "integrations/prometheus/partials/_instance_inventory.html",
    )
    missing = [fragment for fragment in required if fragment not in source]
    assert not missing, f'Prometheus landing workspace is incomplete: {missing}'


def test_prometheus_registry_uses_htmx_filters_and_standard_pagination() -> None:
    wrapper = REGISTRY.read_text(encoding='utf-8')
    content = REGISTRY_CONTENT.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')

    required_wrapper = (
        'Prometheus Connection Registry',
        'hx-target="#prometheus-inventory-content"',
        'hx-trigger="change from:select"',
        'id="prometheus-inventory-loading"',
        'notification-progress-indeterminate',
        'Register Connection',
        'Instances & Bindings',
    )
    missing = [fragment for fragment in required_wrapper if fragment not in wrapper]
    assert not missing, f'Prometheus registry filters are incomplete: {missing}'
    assert '>Apply<' not in wrapper

    required_content = (
        'font-sans text-sm font-normal text-content-secondary',
        'table_label.metadata_label',
        'status_badge(row.compatibility)',
        'status_badge(row.readiness)',
        'Showing <strong',
        'Connections per page',
        'Page {{ pagination.page }} / {{ pagination.total_pages }}',
        "url_for('prometheus.instance_detail', instance_id=row.instance_id)",
    )
    missing = [fragment for fragment in required_content if fragment not in content]
    assert not missing, f'Prometheus registry content is incomplete: {missing}'
    assert "render_template('integrations/prometheus/partials/_inventory_content.html'" in routes


def test_prometheus_instance_detail_is_domain_tabbed() -> None:
    source = DETAIL.read_text(encoding='utf-8')
    required = (
        "('configuration', 'Configuration', 'settings-2')",
        "('validation', 'Validation & Capabilities', 'badge-check')",
        "('runtime', 'Runtime & History', 'activity')",
        "('scope', 'Scope & Resolution', 'waypoints')",
        'Connection Contract',
        'Compatibility &amp; Capability Contract',
        'Technical evidence',
        "prometheus/partials/_runtime_panel.html",
        "prometheus/partials/_runtime_history.html",
        'Scope Bindings',
        'Manage Bindings',
    )
    missing = [fragment for fragment in required if fragment not in source]
    assert not missing, f'Prometheus instance domain tabs are incomplete: {missing}'


def test_prometheus_runtime_history_and_binding_workspace_follow_kaori_violet() -> None:
    runtime = RUNTIME.read_text(encoding='utf-8')
    history = HISTORY.read_text(encoding='utf-8')
    bindings = BINDINGS.read_text(encoding='utf-8')

    required_runtime = (
        'Runtime Health &amp; Diagnostics',
        'Health Interpretation',
        'Diagnostic Pipeline',
        'status_badge',
        'table_label.metadata_label',
        'No action required.',
    )
    missing = [fragment for fragment in required_runtime if fragment not in runtime]
    assert not missing, f'Prometheus runtime workspace is incomplete: {missing}'

    required_history = (
        '100-record retention',
        'Showing <strong',
        'aria-label="Runtime observations per page"',
        'h-9 w-20 rounded-lg',
        'Page {{ runtime_history.pagination.page }} / {{ runtime_history.pagination.total_pages }}',
    )
    missing = [fragment for fragment in required_history if fragment not in history]
    assert not missing, f'Prometheus runtime history is incomplete: {missing}'

    required_bindings = (
        'page_hero.shell_classes()',
        'Prometheus Instances & Bindings',
        'How bindings participate in source resolution',
        'xl:grid-cols-12',
        'xl:col-span-8',
        'xl:sticky xl:top-5 xl:col-span-4',
        '<h3 class="text-base font-semibold text-content-primary">Create Binding</h3>',
        'mb-1.5 block text-sm font-semibold text-content-primary',
        'h-11 w-full rounded-lg',
        'Pre-save validation',
        'Create Binding',
    )
    missing = [fragment for fragment in required_bindings if fragment not in bindings]
    assert not missing, f'Prometheus binding workspace is incomplete: {missing}'


def test_prometheus_cluster_configuration_and_readiness_are_standardized() -> None:
    config = CONFIG.read_text(encoding='utf-8')
    readiness = READINESS.read_text(encoding='utf-8')
    required = (
        'page_hero.shell_classes()',
        'Configuration',
        'Validation & Analytics',
        'Runtime & History',
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
