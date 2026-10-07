from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_TEMPLATES = ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_dashboard_uses_shared_workspace_tabs_and_persists_url_state() -> None:
    source = read('app/templates/kubernetes/dashboard/partials/_content.html')
    selector = read('app/templates/kubernetes/dashboard/partials/_signal_overview.html')
    routes = read('app/kubernetes/dashboard/routes.py')
    application_contract = read('app/dashboards/common/operational.py')
    schema = read('app/kubernetes/dashboard/schema.py')

    framework = read('app/templates/components/operational_dashboard_workspace.html')

    assert 'components/operational_dashboard_workspace.html' in source
    assert 'dashboard_workspace.controller(' in source
    assert 'dashboard_workspace.navigation(' in source
    assert '{% for tab_key, tab_label, tab_icon in dashboard_workspace.standard_tabs %}' in source
    assert source.count('dashboard_workspace.panel(') == 1
    assert 'workspace_tabs.render(standard_tabs' in framework
    assert "url.searchParams.set('tab', tab)" in framework
    assert "window.history.replaceState({}, '', url)" in framework
    assert 'id="{{ input_id }}"' in framework
    assert 'hx-include="#dashboard-active-tab"' in selector
    assert 'normalize_operational_tab' in routes
    assert 'OPERATIONAL_DASHBOARD_TABS: tuple[str, ...] = (' in application_contract
    for tab in ("'overview'", "'capacity'", "'signals'", "'reporting'"):
        assert tab in application_contract
    assert "active_tab: str = 'overview'" in schema


def test_dashboard_uses_integrated_tabs_and_equal_height_peer_content() -> None:
    source = read('app/templates/kubernetes/dashboard/partials/_content.html')
    grid = read('app/templates/components/peer_content_grid.html')
    tabs = read('app/templates/components/workspace_tabs.html')
    framework = read('app/templates/components/operational_dashboard_workspace.html')
    integrated_tabs = tabs.split('{% macro render(', 1)[1].split('{%- endmacro %}', 1)[0]

    overview = read('app/templates/kubernetes/dashboard/partials/_overview.html')
    capacity = read('app/templates/kubernetes/dashboard/partials/_capacity.html')
    signals = read('app/templates/kubernetes/dashboard/partials/_signals.html')
    reporting = read('app/templates/kubernetes/dashboard/partials/_reporting.html')
    sections = (overview, capacity, signals, reporting)

    assert 'components/operational_dashboard_workspace.html' in source
    assert 'data-kaori-dashboard-framework="operational-v1"' in framework
    for section in sections:
        assert '{% import "components/peer_content_grid.html" as peer_content_grid %}' in section
        assert 'peer_content_grid.layout_classes()' in section
    assert "column_classes('primary', 'seven-five')" in reporting
    assert "column_classes('secondary', 'seven-five')" in reporting
    assert 'components/context_rail.html' not in source
    assert 'components/related_page_card.html' not in source
    assert 'xl:grid-cols-12' in grid
    assert 'xl:col-span-6' in grid
    assert 'xl:col-span-7' in grid
    assert 'xl:col-span-5' in grid
    assert 'h-full min-w-0' in grid
    assert 'rounded-xl' not in integrated_tabs
    assert 'bg-surface-card' not in integrated_tabs
    assert 'shadow-sm' not in integrated_tabs
    assert 'border-b border-outline-subtle' in integrated_tabs
    assert 'data-kaori-tab-variant="integrated-workspace"' in integrated_tabs
    assert 'dashboard_workspace.standard_tabs' in source
    assert "('capacity', 'Capacity & Demand', 'gauge')" in framework
    assert "('signals', 'Signals & Actions', 'bell-ring')" in framework
    assert "('reporting', 'Reporting', 'file-text')" in framework


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
        '_alert_response_guidance.html',
    ]

    shared_owners = {
        '_signal_overview.html': 'components/operational_signal_overview.html',
        '_alerts_summary.html': 'components/operational_alert_summary.html',
        '_recommended_actions.html': 'components/operational_recommendation_cards.html',
        '_alert_response_guidance.html': 'components/operational_alert_response.html',
    }
    for name in partials:
        source = (DASHBOARD_TEMPLATES / 'partials' / name).read_text(encoding='utf-8')
        if name in shared_owners:
            assert shared_owners[name] in source, name
        else:
            assert 'components/operational_section_card.html' in source, name
            assert 'operational_section_card.render(' in source, name

    loading = read('app/templates/components/operational_section_loading.html')
    assert 'components/operational_section_card.html' in loading
    assert 'operational_section_card.render(' in loading

    reporting_summary = read('app/templates/kubernetes/dashboard/partials/_reporting_summary.html')
    reporting_guidance = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')
    assert 'components/reporting_dashboard_workspace.html' in reporting_summary
    assert 'components/reporting_dashboard_workspace.html' in reporting_guidance
    assert 'components/operational_section_card.html' in reporting_workspace
    assert reporting_workspace.count('operational_section_card.render(') == 2

    component = read('app/templates/components/operational_section_card.html')
    assert 'text-base font-semibold' in component
    assert 'components/section_link_button.html' in component
    assert 'rounded-xl border border-outline-default bg-surface-card shadow-sm' in component


def test_primary_and_peer_operational_flows_are_static_and_controlled_flows_reuse_governance_sequence() -> None:
    info_flow = read('app/templates/components/info_flow.html')
    flow_steps = read('app/templates/components/operational_flow_steps.html')
    numbered_steps = read('app/templates/components/numbered_governance_steps.html')
    alert_response = read('app/templates/components/operational_alert_response.html')
    alert_guidance = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    reporting_guidance = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')
    capacity = read('app/templates/kubernetes/dashboard/partials/_capacity_snapshot.html')
    contract = read('docs/design/components/OPERATIONAL_FLOW_STEPS.md')

    assert '<section' in info_flow
    assert '<details' not in info_flow
    assert '<summary' not in info_flow
    assert '<details' not in flow_steps
    assert '<details' not in numbered_steps
    assert 'divide-y divide-outline-subtle' in numbered_steps
    assert 'components/operational_alert_response.html' in alert_guidance
    assert 'components/numbered_governance_steps.html' in alert_response
    assert 'components/operational_flow_steps.html' not in alert_guidance
    assert 'components/reporting_dashboard_workspace.html' in reporting_guidance
    assert 'components/numbered_governance_steps.html' not in reporting_workspace
    assert 'components/operational_flow_steps.html' not in reporting_workspace
    assert 'reporting_steps' in reporting_workspace
    assert 'Governed Flow' in reporting_workspace
    assert 'sm:grid-cols-2' in reporting_workspace
    assert 'gap-px overflow-hidden' in reporting_workspace
    assert 'components/operational_flow_steps.html' in capacity
    assert 'components/context_guidance_card.html' not in alert_guidance
    assert 'components/context_guidance_card.html' not in reporting_guidance
    assert 'always visible' in contract


def test_dashboard_and_analytics_share_the_forecast_projection_chart() -> None:
    dashboard = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')
    analytics = read('app/templates/kubernetes/analytics/overview/partials/_forecast_snapshot.html')
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
    source = read('app/templates/kubernetes/dashboard/partials/_cluster_health.html')
    routes = read('app/kubernetes/dashboard/routes.py')
    application_contract = read('app/dashboards/common/operational.py')
    pagination = read('app/common/pagination.py')

    assert '{% import "components/table.html" as table_ui %}' in source
    assert '{% import "components/pagination.html" as pagination_ui %}' in source
    assert 'for size in pagination.allowed_per_page' in source
    assert '[5, 10, 25, 50]' not in source
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
    assert 'normalize_dashboard_page_size' in routes
    assert 'DASHBOARD_PAGE_SIZES = PER_PAGE_OPTIONS' in application_contract
    assert 'PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)' in pagination


def test_dashboard_page_templates_have_no_local_typography_or_shell_drift() -> None:
    sources = []
    for path in sorted(DASHBOARD_TEMPLATES.rglob('*.html')):
        sources.append((path, path.read_text(encoding='utf-8')))

    arbitrary_text = re.compile(r'\btext-\[[^\]]+\]')
    arbitrary_tracking = re.compile(r'\btracking-\[[^\]]+\]')
    copied_shell = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'

    for path, source in sources:
        assert arbitrary_text.search(source) is None, path
        assert arbitrary_tracking.search(source) is None, path
        assert 'font-extrabold' not in source, path
        assert copied_shell not in source, path


def test_dashboard_copy_uses_canonical_casing() -> None:
    all_source = '\n'.join(path.read_text(encoding='utf-8') for path in sorted(DASHBOARD_TEMPLATES.rglob('*.html')))
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')

    assert 'Live Signals Enabled' not in all_source
    assert 'Select a Cluster for Live Signals' not in all_source
    assert 'AlertManager' not in all_source
    assert 'PDF output' not in all_source
    assert 'stored PDF' not in all_source
    assert 'Continue With Alert Detail' not in all_source
    assert 'Continue With Reporting' not in all_source
    assert 'How To Read' not in all_source
    assert 'What To Do' not in all_source
    assert 'What This Summary Means' not in all_source
    assert 'Cluster Signals Available' in all_source
    assert 'Select a Cluster for Detailed Signals' in all_source
    assert 'Generated output' in reporting_workspace
    assert 'Preserve the artifact' in reporting_workspace


def test_dashboard_uses_local_skeletons_and_section_owned_loading_bar() -> None:
    content = read('app/templates/kubernetes/dashboard/partials/_content.html')
    selector = read('app/templates/kubernetes/dashboard/partials/_signal_overview.html')
    loading = read('app/templates/components/operational_section_loading.html')
    cluster_health = read('app/templates/kubernetes/dashboard/partials/_cluster_health.html')
    section_card = read('app/templates/components/operational_section_card.html')
    contract = read('docs/design/components/LOADING.md')

    assert 'dashboard-loading-bar' not in content
    assert 'dashboard-loading-bar' not in selector
    assert 'components/operational_section_loading.html' in content
    assert 'section_loading.section(' in content
    assert 'animate-pulse' in loading
    assert 'loading_bar_active=loading_bar_id is not none' in loading
    assert 'components/loading_bar.html' in section_card
    assert 'dashboard-cluster-health-loading' in cluster_health
    assert 'hx-indicator="#dashboard-cluster-health-loading"' in cluster_health
    assert 'section-owned loading bar' in contract
    assert 'global loading bar' in contract


def test_dashboard_restores_card_grid_freshness_and_visible_action_flows() -> None:
    freshness = read('app/templates/kubernetes/dashboard/partials/_data_freshness.html')
    capacity = read('app/templates/kubernetes/dashboard/partials/_capacity_snapshot.html')
    alert = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    reporting = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')
    evidence_tile = read('app/templates/components/operational_evidence_tile.html')
    alert_response = read('app/templates/components/operational_alert_response.html')

    assert "body_classes='grid gap-3 p-5 sm:grid-cols-2'" in freshness
    assert 'components/operational_evidence_tile.html' in freshness
    assert 'bg-surface-elevated p-3.5' in evidence_tile
    assert 'Recommended Capacity Action Flow' in capacity
    assert 'Controlled Alert Response Flow' in alert
    assert 'Alert Interpretation & Response' in alert_response
    assert 'components/reporting_dashboard_workspace.html' in reporting
    assert 'Reporting Workflow' in reporting_workspace
    assert 'Scope Bound' in reporting_workspace
    assert 'Evidence Backed' in reporting_workspace
    assert 'Review First' in reporting_workspace
    assert 'Governed Flow' in reporting_workspace
    assert 'Execution Mode' in reporting_workspace
    assert 'Reporting Tip' in reporting_workspace
    assert 'Use templates for repeatable report structure.' in reporting_workspace
    assert "body_classes='space-y-4 p-5'" in reporting_workspace
    assert "extra_classes='h-full'" in reporting_workspace
    assert '<details' not in alert
    assert '<details' not in reporting_workspace
    assert "extra_classes='h-full'" in freshness
    assert "extra_classes='h-full'" in capacity
    assert "extra_classes='h-full'" in alert_response


def test_dashboard_tabs_support_canonical_keyboard_navigation() -> None:
    source = read('app/templates/kubernetes/dashboard/partials/_content.html')
    framework = read('app/templates/components/operational_dashboard_workspace.html')
    tabs = read('app/templates/components/workspace_tabs.html')
    contract = read('docs/design/components/WORKSPACE_TABS.md')

    assert 'components/operational_dashboard_workspace.html' in source
    assert 'moveTab(currentTab, direction, prefix)' in framework
    assert '@keydown.arrow-right.prevent' in tabs
    assert '@keydown.arrow-left.prevent' in tabs
    assert '@keydown.home.prevent' in tabs
    assert '@keydown.end.prevent' in tabs
    assert 'Arrow Left/Right move and wrap focus across peer tabs' in contract


def test_dashboard_metric_card_has_no_unused_tone_api() -> None:
    metric_card = read('app/templates/components/operational_metric_card.html')
    kpi_cards = read('app/templates/kubernetes/dashboard/partials/_kpi_cards.html')

    assert (
        "macro render(label, value, description, icon, source_label='Operational', "
        "scope_label='Active Scope')" in metric_card
    )
    assert "tone='violet'" not in metric_card
    assert 'scope_tone' not in metric_card
    assert 'semantic_tones' not in kpi_cards
    assert 'scope_tone' not in kpi_cards


def test_dashboard_pattern_is_locked_by_documentation_and_quality_gate() -> None:
    standard = read('docs/design/patterns/OPERATIONAL_DASHBOARD.md')
    audit = read('docs/design/audits/KUBERNETES_OPERATIONS_DASHBOARD_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    assert '# KAORI Operational Dashboard Pattern v1.7' in standard
    assert '**Status:** Locked reference pattern' in standard
    assert 'No visual redesign is required' in audit
    assert 'python scripts/verify_operational_dashboard_standard.py' in quality_gate
    assert "-m 'not debug and not e2e and not contract and not migration'" in quality_gate


def test_reporting_activity_is_capped_at_four_records() -> None:
    reporting_service = read('app/kubernetes/dashboard/sections/reporting.py')
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')

    assert 'query_all(Report, selected_cluster_id, limit=4)' in reporting_service
    assert 'reporting.latest_reports[:4]' in reporting_workspace
    assert 'Review before reuse.' in reporting_workspace
    assert '<span class="font-semibold text-content-primary">Recurring</span> · Schedule' in reporting_workspace
