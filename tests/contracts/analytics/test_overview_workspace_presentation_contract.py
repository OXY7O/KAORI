from pathlib import Path


OVERVIEW_ROOT = Path('app/templates/analytics/overview')


def read(relative: str) -> str:
    return (OVERVIEW_ROOT / relative).read_text(encoding='utf-8')


def test_overview_controls_and_readiness_share_one_compact_box() -> None:
    source = read('partials/_health_summary.html')
    hero = read('partials/_hero.html')

    assert 'Analytics Controls &amp; Data Readiness' in source
    assert 'id="analytics-overview-filter"' in source
    assert 'h-9 min-w-0 flex-1' in source
    assert 'prometheus_status_panel.render' in source
    assert 'compact=true, flat=true' in source
    assert 'Latest Analytics Data Snapshot' in source
    assert 'Latest Sync' in source
    assert 'Coverage' in source
    assert 'id="analytics-overview-filter"' not in hero


def test_prometheus_compact_mode_avoids_nested_card() -> None:
    source = Path('app/templates/analytics/components/_prometheus_status.html').read_text(encoding='utf-8')

    assert 'flat=false' in source
    assert "'px-0 py-0' if flat" in source
    assert 'data-analytics-prometheus-status' in source
    assert 'rounded-xl' not in source


def test_operational_health_summary_uses_compact_signal_strip_and_guidance() -> None:
    source = read('partials/_health_summary.html')

    assert source.count('<section class="overflow-hidden rounded-xl') == 2
    assert 'Operational Health Summary' in source
    assert '6 Health Signals' in source
    assert 'divide-y divide-outline-subtle' in source
    assert 'Operational Reading' in source
    assert 'Recommended Review Path' in source


def test_overview_workspace_splits_long_domains_into_dedicated_tabs() -> None:
    source = read('index.html')

    assert 'id="analytics-overview-workspace"' in source
    assert "embedded=true" in source
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
            'Operational Reading',
            'Warning Threshold',
            'Critical Threshold',
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
            'Decision Principle',
        ),
    }

    for relative, markers in expectations.items():
        source = read(relative)
        assert 'rounded-2xl border border-brand-outline bg-kaori-primary' not in source
        assert 'grid grid-cols-1 divide-y divide-outline-subtle' in source
        for marker in markers:
            assert marker in source


def test_forecast_snapshot_uses_one_chart_and_one_resource_outlook() -> None:
    source = read('partials/_forecast_snapshot.html')

    assert 'Combined Forecast Projection' in source
    assert 'Resource Outlook' in source
    assert 'How To Read' in source
    assert 'What To Do' in source
    assert 'Warning 75%' in source
    assert 'Critical 90%' in source
    assert source.count('<svg') == 1
    assert 'Trend Interpretation' not in source


def test_top_consumers_use_compact_ranked_rows_without_truncating_identity() -> None:
    source = read('partials/_top_consumers_snapshot.html')

    assert 'Top Consumer Snapshot' in source
    assert 'Ranked Records' in source
    assert 'break-words text-sm font-semibold' in source
    assert 'truncate' not in source
    assert 'How To Read' in source
    assert 'Recommended Action' in source


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
