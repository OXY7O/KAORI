from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_forecast_modules_have_explicit_runtime_ownership() -> None:
    service = read('app/kubernetes/analytics/forecast/service.py')
    calculation = read('app/kubernetes/analytics/forecast/calculation.py')
    presentation = read('app/kubernetes/analytics/forecast/presentation.py')
    resource = read('app/kubernetes/analytics/forecast/resource.py')
    contracts = read('app/kubernetes/analytics/forecast/contracts.py')

    assert len(service.splitlines()) <= 800
    assert len(calculation.splitlines()) <= 800
    assert len(presentation.splitlines()) <= 800
    assert len(resource.splitlines()) <= 800
    assert 'class ForecastAnalysisService' in service
    assert 'def _calculate_forecast(' in calculation
    assert 'def _build_summary(' in calculation
    assert 'def present_forecast_materialized_context(' in presentation
    assert 'WARNING_THRESHOLD = 75.0' in contracts
    assert 'CRITICAL_THRESHOLD = 90.0' in contracts


def test_forecast_empty_payload_imports_canonical_thresholds() -> None:
    presentation = read('app/kubernetes/analytics/forecast/presentation.py')
    import_block = presentation.split(
        'from app.kubernetes.analytics.forecast.contracts import (',
        1,
    )[1].split(')', 1)[0]
    empty_payload_block = presentation.split(
        'def _empty_payload(',
        1,
    )[1].split('def get_forecast_snapshot', 1)[0]

    assert 'WARNING_THRESHOLD' in import_block
    assert 'CRITICAL_THRESHOLD' in import_block
    assert "'warning_threshold': WARNING_THRESHOLD" in empty_payload_block
    assert "'critical_threshold': CRITICAL_THRESHOLD" in empty_payload_block


def test_forecast_snapshot_identity_excludes_local_projection_controls() -> None:
    routes = read('app/kubernetes/analytics/forecast/routes.py')
    catalog = read('app/definitions/catalogs/kubernetes/analytics/datasets.yaml')

    snapshot_block = routes.split('def _snapshot_parameters()', 1)[1].split('def _context_or_state', 1)[0]
    assert "'history_window'" in snapshot_block
    assert "'cluster_id'" in snapshot_block
    assert "'namespace'" in snapshot_block
    assert 'forecast_horizon' not in snapshot_block
    assert "'method'" not in snapshot_block
    assert "'tab'" not in snapshot_block
    assert 'snapshot_parameter_keys:' in catalog


def test_forecast_queries_use_ready_worker_and_duplicate_safe_boundaries() -> None:
    profile = read('app/integrations/observability/metrics_source/query_profiles/forecast_v1.py')

    assert 'max by (namespace, pod, container)' in profile
    assert 'max by (namespace, pod, node)' in profile
    assert 'phase=~"Pending|Running"' in profile
    assert 'kube_node_status_condition{condition="Ready",status="true"}' in profile
    assert 'kube_node_role{role=~"control-plane|master"}' in profile
    assert 'max by (namespace, persistentvolumeclaim)' in profile
    assert profile.count("required_history='90d'") >= 13


def test_forecast_peak_drives_status_and_threshold_eta_uses_projected_points() -> None:
    resource = read('app/kubernetes/analytics/forecast/resource.py')
    calculation = read('app/kubernetes/analytics/forecast/calculation.py')

    assert 'peak = max(' in resource
    assert '_resolve_status(peak_percent)' in resource
    assert 'for point in forecast_points:' in calculation
    assert "f'Beyond {horizon_days}d horizon'" in calculation
    eta_block = calculation.split('def _calculate_threshold_eta', 1)[1].split('def _resolve_summary_posture', 1)[0]
    assert 'slope_per_day' not in eta_block


def test_forecast_limited_evidence_prevents_false_healthy_posture() -> None:
    calculation = read('app/kubernetes/analytics/forecast/calculation.py')
    resource = read('app/kubernetes/analytics/forecast/resource.py')
    template = read('app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html')

    assert "return 'limited', 'Limited Evidence', 'warning'" in calculation
    assert "planning_ready = has_data and signal_quality in {'High', 'Medium'}" in resource
    assert "'Limited Evidence'" in resource
    assert 'not for an authoritative capacity commitment' in template


def test_forecast_chart_aligns_series_by_timestamp_and_keeps_missing_points_null() -> None:
    calculation = read('app/kubernetes/analytics/forecast/calculation.py')
    runtime = read('app/static/js/kubernetes/analytics/forecast_chart.js')

    assert 'all_dates = sorted(' in calculation
    assert "'historical': [historical_map.get(date) for date in all_dates]" in calculation
    assert "'forecast': [forecast_map.get(date) for date in all_dates]" in calculation
    assert 'labels = payload?.labels || available[0].labels || []' in runtime
    assert 'spanGaps: false' in runtime
    assert 'suggestedMax' in runtime


def test_forecast_legacy_partial_route_is_removed() -> None:
    routes = read('app/kubernetes/analytics/forecast/routes.py')
    analytics_routes = read('app/analytics/routes.py')
    navigation = read('app/templates/components/navigation/analytics_menu.html')

    assert 'def forecast_section(' not in routes
    assert "'/forecast/section'" not in analytics_routes
    assert 'analytics.forecast_section' not in navigation


def test_forecast_report_uses_canonical_thresholds_and_peak_projection() -> None:
    report = read('app/reports/export/html_pdf/forecast_analysis.py')
    payload = read('app/reports/export/payloads/forecast.py')

    assert 'from app.kubernetes.analytics.forecast.contracts import CRITICAL_THRESHOLD, WARNING_THRESHOLD' in report
    assert "'setting': '75% / 90%'" in report
    assert "'warning': '75%'" in report
    assert "'critical': '90%'" in report
    assert "_float(item.get('peak_projected_percent')) or 0.0) >= _WARNING_THRESHOLD" in report
    assert "_float(item.get('peak_projected_percent')) or 0.0) >= _CRITICAL_THRESHOLD" in report
    assert "'freshness': '75% / 90%'" in payload
    assert payload.count("'has_data': False") == 1
