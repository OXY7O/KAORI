from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_TEMPLATES = ROOT / 'app' / 'templates' / 'dashboards' / 'kubernetes'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_dashboard_uses_shared_workspace_tabs_and_persists_url_state() -> None:
    source = read('app/templates/dashboards/kubernetes/partials/_content.html')
    selector = read('app/templates/dashboards/kubernetes/partials/_signal_overview.html')
    routes = read('app/dashboards/kubernetes/routes.py')
    schema = read('app/dashboards/kubernetes/schema.py')

    assert '{% import "components/workspace_tabs.html" as workspace_tabs %}' in source
    assert 'workspace_tabs.render(' in source
    assert "url.searchParams.set('tab', tab)" in source
    assert "window.history.replaceState({}, '', url)" in source
    assert 'id="dashboard-active-tab"' in source
    assert 'hx-include="#dashboard-active-tab"' in selector
    assert "DASHBOARD_TABS = {'overview', 'capacity', 'signals', 'reporting'}" in routes
    assert "active_tab: str = 'overview'" in schema


def test_dashboard_uses_integrated_tabs_and_equal_height_peer_content() -> None:
    source = read('app/templates/dashboards/kubernetes/partials/_content.html')
    grid = read('app/templates/components/peer_content_grid.html')
    tabs = read('app/templates/components/workspace_tabs.html')

    assert '{% import "components/peer_content_grid.html" as peer_content_grid %}' in source
    assert source.count('peer_content_grid.layout_classes()') == 4
    assert "column_classes('primary', 'seven-five')" in source
    assert "column_classes('secondary', 'seven-five')" in source
    assert 'components/context_rail.html' not in source
    assert 'components/related_page_card.html' not in source
    assert 'xl:grid-cols-12' in grid
    assert 'xl:col-span-6' in grid
    assert "xl:col-span-7" in grid
    assert "xl:col-span-5" in grid
    assert 'h-full min-w-0' in grid
    assert 'rounded-xl' not in tabs
    assert 'bg-surface-card' not in tabs
    assert 'shadow-sm' not in tabs
    assert 'border-b border-outline-subtle' in tabs
    assert 'data-kaori-tab-variant="integrated-workspace"' in tabs
    assert 'id="kubernetes-dashboard-panel-capacity"' in source
    assert 'id="kubernetes-dashboard-panel-signals"' in source
    assert 'id="kubernetes-dashboard-panel-reporting"' in source


def test_dashboard_sections_use_the_canonical_operational_section_card() -> None:
    partials = [
        '_signal_overview.html',
        '_cluster_health.html',
        '_inventory_summary.html',
        '_data_freshness.html',
        '_capacity_snapshot.html',
        '_forecast_risk.html',
        '_top_consumers.html',
        '_alerts_summary.html',
        '_recommended_actions.html',
        '_reporting_summary.html',
        '_alert_response_guidance.html',
        '_reporting_guidance.html',
        '_section_loading.html',
    ]

    for name in partials:
        source = (DASHBOARD_TEMPLATES / 'partials' / name).read_text(encoding='utf-8')
        assert 'components/operational_section_card.html' in source, name
        assert 'operational_section_card.render(' in source, name

    component = read('app/templates/components/operational_section_card.html')
    assert 'text-base font-semibold' in component
    assert 'components/section_link_button.html' in component
    assert 'rounded-xl border border-outline-default bg-surface-card shadow-sm' in component


def test_primary_and_peer_operational_flows_are_static() -> None:
    info_flow = read('app/templates/components/info_flow.html')
    flow_steps = read('app/templates/components/operational_flow_steps.html')
    alert_guidance = read(
        'app/templates/dashboards/kubernetes/partials/_alert_response_guidance.html'
    )
    reporting_guidance = read(
        'app/templates/dashboards/kubernetes/partials/_reporting_guidance.html'
    )
    capacity = read(
        'app/templates/dashboards/kubernetes/partials/_capacity_snapshot.html'
    )
    contract = read('docs/design/components/OPERATIONAL_FLOW_STEPS.md')

    assert '<section' in info_flow
    assert '<details' not in info_flow
    assert '<summary' not in info_flow
    assert '<details' not in flow_steps
    assert 'components/operational_flow_steps.html' in alert_guidance
    assert 'components/operational_flow_steps.html' in reporting_guidance
    assert 'components/operational_flow_steps.html' in capacity
    assert 'components/context_guidance_card.html' not in alert_guidance
    assert 'components/context_guidance_card.html' not in reporting_guidance
    assert 'always visible' in contract


def test_dashboard_and_analytics_share_the_forecast_projection_chart() -> None:
    dashboard = read('app/templates/dashboards/kubernetes/partials/_forecast_risk.html')
    analytics = read('app/templates/analytics/overview/partials/_forecast_snapshot.html')
    component = read('app/templates/components/forecast_projection_chart.html')

    assert 'components/forecast_projection_chart.html' in dashboard
    assert 'forecast_projection_chart.render(' in dashboard
    assert 'components/forecast_projection_chart.html' in analytics
    assert 'forecast_projection_chart.render(' in analytics
    assert '<svg' not in dashboard
    assert '<svg' not in analytics
    assert '<svg' in component
    assert 'Warning 75%' in component
    assert 'Critical 90%' in component


def test_cluster_health_uses_canonical_table_and_pagination_contract() -> None:
    source = read('app/templates/dashboards/kubernetes/partials/_cluster_health.html')
    routes = read('app/dashboards/kubernetes/routes.py')

    assert '{% import "components/table.html" as table_ui %}' in source
    assert '{% import "components/pagination.html" as pagination_ui %}' in source
    assert 'for size in [5, 10, 25, 50]' in source
    assert 'pagination_ui.numeric_pages(' in source
    assert 'pagination_ui.navigation_classes()' in source
    assert 'pagination_ui.navigation_classes(disabled=true)' in source
    assert 'aria-disabled="true"' in source
    assert 'hx-include="#cluster-health-scope, #cluster-health-page-reset"' in source
    assert source.count('hx-disabled-elt="this"') == 3
    assert source.count('hx-indicator="#dashboard-cluster-health-loading"') == 3
    assert "loading_bar_id='dashboard-cluster-health-loading'" in source
    assert 'of {{ pagination.total_items }} Clusters' in source
    assert 'of {{ pagination.total_items }} clusters' not in source
    assert "url_for('integrations.kubernetes')" in source
    assert "url_for('cluster.list_clusters')" not in source
    assert 'CLUSTER_HEALTH_PAGE_SIZES = {5, 10, 25, 50}' in routes
    assert "request.args.get('cluster_health_per_page', '5')" in routes


def test_dashboard_page_templates_have_no_local_typography_or_shell_drift() -> None:
    sources = []
    for path in sorted(DASHBOARD_TEMPLATES.rglob('*.html')):
        sources.append((path, path.read_text(encoding='utf-8')))

    arbitrary_text = re.compile(r'\btext-\[[^\]]+\]')
    arbitrary_tracking = re.compile(r'\btracking-\[[^\]]+\]')
    copied_shell = (
        'overflow-hidden rounded-xl border border-outline-default '
        'bg-surface-card shadow-sm'
    )

    for path, source in sources:
        assert arbitrary_text.search(source) is None, path
        assert arbitrary_tracking.search(source) is None, path
        assert 'font-extrabold' not in source, path
        assert copied_shell not in source, path


def test_dashboard_copy_uses_canonical_casing() -> None:
    all_source = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted(DASHBOARD_TEMPLATES.rglob('*.html'))
    )

    assert 'Select A Cluster For Live Signals' not in all_source
    assert 'AlertManager' not in all_source
    assert 'Continue With Alert Detail' not in all_source
    assert 'Continue With Reporting' not in all_source
    assert 'How To Read' not in all_source
    assert 'What To Do' not in all_source
    assert 'Select a Cluster for Live Signals' in all_source


def test_dashboard_uses_local_skeletons_and_section_owned_loading_bar() -> None:
    content = read('app/templates/dashboards/kubernetes/partials/_content.html')
    selector = read('app/templates/dashboards/kubernetes/partials/_signal_overview.html')
    loading = read('app/templates/dashboards/kubernetes/partials/_section_loading.html')
    cluster_health = read('app/templates/dashboards/kubernetes/partials/_cluster_health.html')
    section_card = read('app/templates/components/operational_section_card.html')
    contract = read('docs/design/components/LOADING.md')

    assert 'dashboard-loading-bar' not in content
    assert 'dashboard-loading-bar' not in selector
    assert 'animate-pulse' in loading
    assert 'loading_bar_active=loading_bar_id is not none' in loading
    assert 'components/loading_bar.html' in section_card
    assert 'dashboard-cluster-health-loading' in cluster_health
    assert 'hx-indicator="#dashboard-cluster-health-loading"' in cluster_health
    assert 'section-owned loading bar' in contract
    assert 'global loading bar' in contract


def test_dashboard_restores_card_grid_freshness_and_visible_action_flows() -> None:
    freshness = read('app/templates/dashboards/kubernetes/partials/_data_freshness.html')
    capacity = read('app/templates/dashboards/kubernetes/partials/_capacity_snapshot.html')
    alert = read('app/templates/dashboards/kubernetes/partials/_alert_response_guidance.html')
    reporting = read('app/templates/dashboards/kubernetes/partials/_reporting_guidance.html')

    assert "body_classes='grid gap-3 p-5 sm:grid-cols-2'" in freshness
    assert 'bg-surface-elevated p-3.5' in freshness
    assert 'Recommended Capacity Action Flow' in capacity
    assert 'Controlled Alert Response Flow' in alert
    assert 'Controlled Reporting Flow' in reporting
    assert 'Reporting Tip' in reporting
    assert 'Use schedules for recurring operational evidence.' in reporting
    assert "icon='lightbulb'" in reporting
    assert '<details' not in alert
    assert '<details' not in reporting
    assert "extra_classes='h-full'" in freshness
    assert "extra_classes='h-full'" in capacity
    assert "extra_classes='h-full'" in alert
    assert "extra_classes='h-full'" in reporting
