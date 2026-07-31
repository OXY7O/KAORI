from pathlib import Path


OVERVIEW_ROOT = Path('app/templates/analytics/overview')


def read(relative: str) -> str:
    return (OVERVIEW_ROOT / relative).read_text(encoding='utf-8')


def test_overview_controls_and_readiness_follow_shared_analytics_standard() -> None:
    source = read('partials/_health_summary.html')
    hero = read('partials/_hero.html')

    assert 'class="space-y-6"' in source
    assert 'data-analytics-controls-readiness' in source
    assert 'Analytics Overview</p>' in source
    assert 'Analytics Controls &amp; Data Readiness' in source
    assert 'id="analytics-overview-filter"' in source
    assert 'h-10 w-full rounded-lg border border-outline-default' in source
    assert 'prometheus_status_panel.render' in source
    assert 'embedded=true' not in source
    assert 'payload.last_analyzed_at, flat=true, compact=true' in source
    assert 'Latest Analytics Data Snapshot' in source
    assert 'Committed worker datasets used by the overview tabs.' in source
    assert 'Coverage' in source
    assert 'id="analytics-overview-filter"' not in hero


def test_prometheus_compact_mode_avoids_nested_card() -> None:
    source = Path('app/templates/analytics/components/_prometheus_status.html').read_text(encoding='utf-8')

    assert 'flat=false' in source
    assert "'px-0 py-0' if flat" in source
    assert 'data-analytics-prometheus-status' in source
    assert 'rounded-xl' not in source


def test_operational_health_summary_has_separate_vertical_rhythm() -> None:
    source = read('partials/_health_summary.html')

    assert source.count('snapshot_panel.render(') == 1
    assert '<section class="overflow-hidden rounded-xl' in source
    assert 'class="space-y-6"' in source
    assert 'Operational Health Summary' in source
    assert '6 Health Signals' in source
    assert "{% elif slot == 'footer' %}" in source
    assert 'Operational Reading' in source
    assert 'Recommended Review Path' in source


def test_overview_workspace_splits_long_domains_into_dedicated_tabs() -> None:
    source = read('index.html')

    assert 'id="analytics-overview-workspace"' in source
    assert 'embedded=true' in source
    assert 'class="p-4 sm:p-5"' in source

    for tab_id, label in (
        ('utilization', 'Utilization'),
        ('capacity', 'Capacity'),
        ('workloads', 'Workloads'),
        ('storage', 'Storage'),
        ('consumers', 'Consumers'),
        ('forecast', 'Forecast'),
        ('alerts', 'Alerts'),
        ('action-summary', 'Action Summary'),
        ('recommendations', 'Recommendations'),
    ):
        assert f"('{tab_id}', '{label}'" in source
        assert f'id="overview-content-panel-{tab_id}"' in source

    for old_label in (
        'Resource & Capacity',
        'Workloads & Storage',
        'Forecast & Signals',
        'Actions & Recommendations',
    ):
        assert old_label not in source


def test_overview_domain_snapshots_are_informative_and_compact() -> None:
    expectations = {
        'partials/_resource_snapshot.html': (
            'Current Resource Pressure',
            'Pressure Posture',
            'How To Read',
            'What To Do',
        ),
        'partials/_capacity_snapshot.html': (
            'Worker Capacity Snapshot',
            'How To Read',
            'Recommended Action',
        ),
        'partials/_workload_snapshot.html': (
            'Resource Governance Findings',
            'Request Coverage',
            'Limit Coverage',
            'Recommended Action',
        ),
        'partials/_storage_snapshot.html': (
            'PVC Capacity Utilization',
            'Storage Risk Context',
            'Recommended Action',
        ),
        'partials/_alerts_snapshot.html': (
            'Alert Triage Queue',
            'Immediate Review',
            'Planned Follow-Up',
            'Anomaly Context',
        ),
        'partials/_actionable_recommendation_summary.html': (
            'Recommendation Source Queue',
            'Operational Triage',
            'Before Execution',
            'Next Review Focus',
            'Decision Principle',
        ),
    }

    for relative, markers in expectations.items():
        source = read(relative)
        assert 'rounded-2xl border border-brand-outline bg-kaori-primary' not in source
        assert 'snapshot_panel.render(' in source
        assert "{% call(slot) snapshot_panel.render(" in source
        for marker in markers:
            assert marker in source



def test_overview_tabs_are_scrollable_and_load_on_first_activation() -> None:
    source = read('index.html')
    tabs = Path('app/templates/analytics/components/_content_tabs.html').read_text(encoding='utf-8')
    controls = Path('app/static/js/analytics_controls.js').read_text(encoding='utf-8')

    assert 'scrollable=true' in source
    assert 'data-analytics-tab-lazy' in source
    assert 'hx-trigger="kaori:analytics-tab-activate"' in source
    assert 'flex w-max min-w-full flex-nowrap gap-2' in tabs
    assert 'data-analytics-tab-scroll' in tabs
    assert "target.dataset.analyticsTabLoadState = 'requesting'" in controls
    assert "window.htmx.trigger(target, 'kaori:analytics-tab-activate')" in controls


def test_snapshot_panel_is_the_shared_overview_surface_standard() -> None:
    component = Path('app/templates/analytics/components/_snapshot_panel.html').read_text(encoding='utf-8')

    assert 'data-analytics-snapshot-panel' in component
    assert 'data-analytics-snapshot-metrics' in component
    assert 'data-analytics-snapshot-body' in component
    assert 'data-analytics-snapshot-footer' in component
    assert 'text-[10px]' not in component
    assert 'tracking-[' not in component
    assert 'h-4.5' not in component

def test_utilization_pressure_visual_is_not_compressed_into_small_cards() -> None:
    source = read('partials/_resource_snapshot.html')

    assert 'xl:grid-cols-12' in source
    assert 'xl:col-span-8' in source
    assert 'xl:col-span-4' in source
    assert 'Headroom' in source
    assert 'Normal · Below 75%' in source
    assert 'Warning · 75% To 90%' in source
    assert 'Critical · Above 90%' in source
    assert 'grid-cols-4 gap-3' not in source


def test_forecast_snapshot_uses_one_chart_and_one_resource_outlook() -> None:
    source = read('partials/_forecast_snapshot.html')
    shared_chart = (
        OVERVIEW_ROOT.parents[1] / 'components/forecast_projection_chart.html'
    ).read_text(encoding='utf-8')

    assert 'Combined Forecast Projection' in source
    assert 'Resource Outlook' in source
    assert 'How to Read' in source
    assert 'What to Do' in source
    assert 'components/forecast_projection_chart.html' in source
    assert 'forecast_projection_chart.render(' in source
    assert 'Warning 75%' in shared_chart
    assert 'Critical 90%' in shared_chart
    assert source.count('<svg') == 0
    assert shared_chart.count('<svg') == 1
    assert 'Trend Interpretation' not in source


def test_top_consumers_use_calm_ranked_surfaces_without_divider_noise() -> None:
    source = read('partials/_top_consumers_snapshot.html')

    assert 'Top Consumer Snapshot' in source
    assert 'Ranked Records' in source
    assert 'grid gap-5 p-4 sm:p-5 xl:grid-cols-2 2xl:grid-cols-4' in source
    assert '<ol class="mt-3 space-y-2"' in source
    assert 'rounded-lg bg-surface-hover px-3 py-2.5' in source
    assert 'break-words text-sm font-semibold' in source
    assert 'progress_bar' not in source
    assert 'divide-y divide-outline-subtle' not in source
    assert 'truncate' not in source
    assert 'How To Read' in source
    assert 'Recommended Action' in source


def test_action_summary_fills_triage_column_with_execution_context() -> None:
    source = read('partials/_actionable_recommendation_summary.html')

    assert 'Before Execution' in source
    assert 'Confirm Accountable Owner' in source
    assert 'Validate Current Evidence' in source
    assert 'Prepare Change And Rollback' in source
    assert 'Next Review Focus' in source
    assert 'highest_source.label' in source
    assert 'highest_source.count' in source


def test_overview_recommendations_are_always_visible_and_paginated() -> None:
    for filename in (
        'partials/_actionable_recommendation_summary.html',
        'partials/_recommendations.html',
    ):
        source = read(filename)
        assert '<details' not in source
        assert '<summary' not in source
        assert 'group-open:' not in source

    recommendations = read('partials/_recommendations.html')
    assert 'data-kaori-recommendation-pager' in recommendations
    assert 'data-page-size="3"' in recommendations
    assert "recommendation_pager.controls(recommendations|length, 'Actions', 3)" in recommendations


def test_overview_tabs_are_scrollable_and_lazy_on_first_activation() -> None:
    source = read('index.html')
    tabs = Path('app/templates/analytics/components/_content_tabs.html').read_text(encoding='utf-8')
    runtime = Path('app/static/js/analytics_controls.js').read_text(encoding='utf-8')

    assert 'scrollable=true' in source
    assert source.count('data-analytics-tab-lazy') == 9
    assert source.count('hx-trigger="kaori:analytics-tab-activate"') == 9
    assert 'load delay:250ms' not in source
    assert 'overflow-x-auto' in tabs
    assert 'flex w-max min-w-full flex-nowrap gap-2' in tabs
    assert 'function requestAnalyticsTabPanel(panel)' in runtime
    assert "window.htmx.trigger(target, 'kaori:analytics-tab-activate')" in runtime
    assert "data.analyticsTabLoadState = 'requesting'" not in runtime
    assert "target.dataset.analyticsTabLoadState = 'requesting'" in runtime


def test_overview_uses_normalized_typography_icons_and_snapshot_component() -> None:
    component = Path('app/templates/analytics/components/_snapshot_panel.html').read_text(encoding='utf-8')
    overview_sources = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in OVERVIEW_ROOT.rglob('*.html')
    )

    assert 'data-analytics-snapshot-panel' in component
    assert 'data-analytics-snapshot-metrics' in component
    assert 'data-analytics-snapshot-body' in component
    assert 'data-analytics-snapshot-footer' in component
    assert 'text-[10px]' not in overview_sources
    assert 'tracking-[' not in overview_sources
    assert 'h-4.5' not in overview_sources
    assert 'w-4.5' not in overview_sources
