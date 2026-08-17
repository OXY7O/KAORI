from pathlib import Path

STATUS_FILES = [
    'app/templates/kubernetes/analytics/overview/partials/_resource_snapshot.html',
    'app/templates/kubernetes/analytics/overview/partials/_storage_snapshot.html',
    'app/templates/kubernetes/analytics/components/_resource_pressure_lane.html',
    'app/templates/kubernetes/analytics/utilization/partials/_overview.html',
    'app/templates/kubernetes/analytics/utilization/partials/_trend.html',
    'app/templates/kubernetes/analytics/utilization/partials/_node_detail.html',
    'app/templates/kubernetes/analytics/storage/partials/_overview.html',
    'app/templates/kubernetes/analytics/storage/partials/_filesystem_panel.html',
    'app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html',
    'app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html',
    'app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html',
    'app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html',
    'app/templates/kubernetes/analytics/alerts/partials/_ownership_summary.html',
    'app/templates/kubernetes/analytics/alerts/partials/_incident_readiness.html',
]


def test_progress_component_owns_semantic_bar_colors():
    component = Path('app/templates/components/progress_bar.html').read_text()
    assert 'macro semantic_bar' in component
    assert 'macro semantic_fill_classes' in component
    assert 'bg-status-normal' in component
    assert 'bg-status-warning' in component
    assert 'bg-status-critical' in component
    assert 'bg-status-unknown' in component
    assert 'bg-status-info' in component


def test_status_related_analytics_bars_use_semantic_renderer():
    for filename in STATUS_FILES:
        source = Path(filename).read_text()
        assert 'progress_bar.semantic_bar(' in source, filename


def test_composition_bars_remain_violet_and_capacity_status_bars_are_semantic():
    materialization = Path('app/templates/kubernetes/analytics/materialization/_pending.html').read_text()
    ranked = Path('app/templates/kubernetes/analytics/components/_ranked_evidence_panel.html').read_text()
    consumers = Path(
        'app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_results.html'
    ).read_text()
    capacity_paths = (
        'app/templates/kubernetes/analytics/capacity/partials/_overview.html',
        'app/templates/kubernetes/analytics/capacity/partials/_allocation.html',
        'app/templates/kubernetes/analytics/capacity/partials/_risk.html',
    )
    assert 'bg-kaori-primary' in materialization
    assert 'bg-kaori-primary' in ranked
    assert 'bg-kaori-primary' in consumers
    for path in capacity_paths:
        source = Path(path).read_text()
        assert 'progress_bar.semantic_bar' in source, path
        assert 'capacity status' in source or 'allocation status' in source or 'headroom status' in source, path


def test_alert_routing_only_semanticizes_severity_distribution():
    source = Path('app/templates/kubernetes/analytics/alerts/partials/_routing_summary.html').read_text()
    assert "title == 'Severity Distribution'" in source
    assert 'progress_bar.semantic_bar(' in source
    assert "label=title ~ ' distribution'" in source
