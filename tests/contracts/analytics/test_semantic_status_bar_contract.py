from pathlib import Path

STATUS_FILES = [
    'app/templates/analytics/components/_resource_pressure_lane.html',
    'app/templates/analytics/utilization/partials/_overview.html',
    'app/templates/analytics/utilization/partials/_trend.html',
    'app/templates/analytics/utilization/partials/_node_detail.html',
    'app/templates/analytics/storage/partials/_overview.html',
    'app/templates/analytics/storage/partials/_filesystem_panel.html',
    'app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html',
    'app/templates/analytics/workload/partials/_tenant_quota_section.html',
    'app/templates/analytics/workload/partials/_workload_mapping_section.html',
    'app/templates/analytics/forecast/partials/_forecast_section.html',
    'app/templates/analytics/alerts/partials/_ownership_summary.html',
    'app/templates/analytics/alerts/partials/_incident_readiness.html',
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


def test_neutral_progress_and_composition_bars_remain_violet():
    materialization = Path('app/templates/analytics/materialization/_pending.html').read_text()
    ranked = Path('app/templates/analytics/components/_ranked_evidence_panel.html').read_text()
    consumers = Path('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html').read_text()
    capacity_paths = (
        'app/templates/analytics/capacity/partials/_overview.html',
        'app/templates/analytics/capacity/partials/_allocation.html',
        'app/templates/analytics/capacity/partials/_risk.html',
    )
    assert 'bg-kaori-primary' in materialization
    assert 'bg-kaori-primary' in ranked
    assert 'bg-kaori-primary' in consumers
    for path in capacity_paths:
        source = Path(path).read_text()
        assert 'bg-kaori-primary' in source, path
        assert 'progress_bar.semantic_bar(' not in source, path


def test_alert_routing_only_semanticizes_severity_distribution():
    source = Path('app/templates/analytics/alerts/partials/_routing_summary.html').read_text()
    assert "title == 'Severity Distribution'" in source
    assert 'progress_bar.semantic_bar(' in source
    assert "label=title ~ ' distribution'" in source
