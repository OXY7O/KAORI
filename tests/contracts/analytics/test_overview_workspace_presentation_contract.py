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

    assert source.count('<section class="overflow-hidden rounded-xl') == 2
    assert 'class="space-y-6"' in source
    assert 'Operational Health Summary' in source
    assert '6 Health Signals' in source
    assert 'divide-y divide-outline-subtle' in source
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
        assert 'overview_surface.snapshot_shell_classes()' in source
        assert 'overview_surface.snapshot_header_classes()' in source
        assert 'overview_surface.snapshot_header_icon_classes()' in source
        for marker in markers:
            assert marker in source


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
    assert "overview_surface.ranked_item_classes('px-3 py-2.5')" in source
    assert "overview_surface.empty_evidence_classes('mt-3 px-4 py-6 text-center')" in source
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



def test_overview_hero_attention_uses_the_full_width_bottom_slot() -> None:
    source = read('partials/_hero_posture.html')
    loading = read('partials/_hero_posture_loading.html')
    shared_hero = Path('app/templates/components/page_hero.html').read_text(encoding='utf-8')

    assert 'page_hero.context_bottom_notice(posture_short_description, posture_tone)' in source
    assert source.index('context_bottom_notice') > source.index('context_metric_card_classes')
    assert 'page_hero.context_posture_note' not in source
    assert 'macro context_bottom_notice' in shared_hero
    assert 'min-h-10 w-full' in shared_hero
    assert 'min-h-10 w-full' in loading


def test_overview_readiness_and_interpretation_surface_hierarchy_is_canonical() -> None:
    health = read('partials/_health_summary.html')
    resource = read('partials/_resource_snapshot.html')
    capacity = read('partials/_capacity_snapshot.html')
    workload = read('partials/_workload_snapshot.html')
    top_consumers = read('partials/_top_consumers_snapshot.html')
    surfaces = Path('app/templates/analytics/components/_overview_surfaces.html').read_text(encoding='utf-8')

    assert 'overview_surface.readiness_shell_classes()' in health
    assert 'overview_surface.attention_strip_classes()' in health
    assert 'overview_surface.interpretation_grid_classes()' in health
    assert 'bg-surface-card' in surfaces
    assert 'bg-surface-hover' in surfaces
    assert "overview_surface.context_panel_classes('border-t border-outline-subtle px-4 py-4 sm:px-5 xl:col-span-4" in resource
    assert 'overview_surface.interpretation_grid_classes()' in resource
    assert 'overview_surface.interpretation_grid_classes()' in capacity
    assert 'overview_surface.interpretation_panel_classes' in workload
    assert 'overview_surface.interpretation_grid_classes()' in top_consumers


def test_overview_status_tones_use_shared_semantic_normalization() -> None:
    health = read('partials/_health_summary.html')
    resource = read('partials/_resource_snapshot.html')
    capacity = read('partials/_capacity_snapshot.html')
    workload = read('partials/_workload_snapshot.html')
    storage = read('partials/_storage_snapshot.html')
    action_summary = read('partials/_actionable_recommendation_summary.html')
    recommendations = read('partials/_recommendations.html')
    table_label = Path('app/templates/components/table_label.html').read_text(encoding='utf-8')

    assert 'table_label.semantic_tone(signal.tone or signal.status)|trim' in health
    assert 'table_label.semantic_tone(item.tone or item.status)|trim' in health
    assert 'table_label.semantic_tone(item.tone or item.status)|trim' in resource
    assert 'table_label.semantic_tone(item.tone or item.status)|trim' in capacity
    assert 'table_label.semantic_tone(workload.tone or workload.status)|trim' in workload
    assert 'table_label.semantic_tone(storage.tone or storage.status)|trim' in storage
    assert 'table_label.semantic_tone(summary.tone or summary.status)|trim' in action_summary
    assert 'table_label.semantic_tone(recommendation.severity_tone or recommendation.severity)|trim' in recommendations
    for alias in ('green', 'amber', 'red', 'gray', 'blue', 'purple'):
        assert alias in table_label



def test_overview_loading_tracker_reports_real_lazy_section_progress() -> None:
    index = read('index.html')
    hero = read('partials/_hero.html')
    tracker = read('partials/_load_tracker.html')
    health = read('partials/_health_summary.html')
    loading_bar = Path('app/templates/components/loading_bar.html').read_text(encoding='utf-8')
    stylesheet = Path('frontend/styles.css').read_text(encoding='utf-8')

    assert 'analytics/overview/partials/_load_tracker.html' in index
    assert index.count('data-overview-lazy-section="true"') == 10
    assert 'data-overview-lazy-section="true"' in hero
    assert 'data-overview-load-state="pending"' in index
    assert 'data-overview-load-state="pending"' in hero
    assert 'data-overview-refresh-request="true"' in health
    assert "document.body.addEventListener('htmx:beforeRequest'" in tracker
    assert "document.body.addEventListener('htmx:afterSettle'" in tracker
    assert "completed + '/' + total + ' Sections'" in tracker
    assert "section.dataset.overviewLoadState = 'failed'" in tracker
    assert 'kaori-loading-bar-segment' in loading_bar
    assert '@keyframes kaori-loading-bar-indeterminate' in stylesheet


def test_capacity_is_the_shared_overview_snapshot_style_baseline() -> None:
    surfaces = Path('app/templates/analytics/components/_overview_surfaces.html').read_text(encoding='utf-8')
    panel_files = (
        'partials/_resource_snapshot.html',
        'partials/_capacity_snapshot.html',
        'partials/_workload_snapshot.html',
        'partials/_storage_snapshot.html',
        'partials/_top_consumers_snapshot.html',
        'partials/_forecast_snapshot.html',
        'partials/_alerts_snapshot.html',
        'partials/_actionable_recommendation_summary.html',
        'partials/_recommendations.html',
    )

    for marker in (
        'macro snapshot_shell_classes',
        'macro snapshot_header_classes',
        'macro snapshot_header_icon_classes',
        'macro metric_grid_classes',
        'macro metric_cell_classes',
        'macro ranked_item_classes',
        'macro guidance_card_classes',
    ):
        assert marker in surfaces

    for relative in panel_files:
        source = read(relative)
        assert 'data-analytics-overview-panel=' in source
        assert 'overview_surface.snapshot_shell_classes()' in source
        assert 'overview_surface.snapshot_header_classes()' in source
        assert 'overview_surface.snapshot_header_icon_classes()' in source

    for relative in (
        'partials/_resource_snapshot.html',
        'partials/_capacity_snapshot.html',
        'partials/_workload_snapshot.html',
        'partials/_storage_snapshot.html',
        'partials/_forecast_snapshot.html',
        'partials/_alerts_snapshot.html',
        'partials/_actionable_recommendation_summary.html',
    ):
        source = read(relative)
        assert 'overview_surface.metric_grid_classes(' in source
        assert 'overview_surface.metric_cell_classes()' in source


def test_primary_overview_evidence_stays_bright_and_guidance_is_bounded() -> None:
    consumers = read('partials/_top_consumers_snapshot.html')
    forecast = read('partials/_forecast_snapshot.html')
    storage = read('partials/_storage_snapshot.html')
    alerts = read('partials/_alerts_snapshot.html')
    action_summary = read('partials/_actionable_recommendation_summary.html')

    assert "overview_surface.ranked_item_classes('px-3 py-2.5')" in consumers
    assert "surface_classes='bg-surface-card'" in forecast
    assert 'overview_surface.guidance_card_classes' in forecast
    assert 'overview_surface.guidance_card_classes' in storage
    assert 'overview_surface.guidance_card_classes' in alerts
    assert 'overview_surface.nested_evidence_card_classes' in action_summary
