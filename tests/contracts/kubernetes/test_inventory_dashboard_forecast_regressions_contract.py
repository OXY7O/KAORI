from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_context_uses_unified_resource_sheet_typography() -> None:
    detail = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    for token in (
        "detail.inventory_row('Environment'",
        "detail.inventory_row('Kubernetes Version'",
        "detail.inventory_row('Registered Cluster'",
        "detail.inventory_row('Last Collected'",
        "detail.inventory_row('Freshness Window'",
        "detail.inventory_row('Snapshot Source'",
    ):
        assert token in detail
    assert 'side_drawer' not in detail
    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared


def test_kubernetes_dashboard_forecast_schema_matches_latest_daily_average_payload() -> None:
    schema = read('app/kubernetes/dashboard/schema.py')
    builder = read('app/kubernetes/dashboard/sections/forecast.py')
    template = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')

    forecast_item = schema.split('class ForecastItem:', 1)[1].split('@dataclass', 1)[0]
    assert 'latest_daily_average_percent: float | None = None' in forecast_item
    assert 'current_percent:' not in forecast_item
    assert 'latest_daily_average_percent=current' in builder
    assert 'item.latest_daily_average_percent' in template


def test_dashboard_operator_guidance_copy_is_compact_and_source_aware() -> None:
    forecast = read('app/kubernetes/dashboard/utils.py')
    consumers = read('app/kubernetes/dashboard/sections/top_consumers.py')
    response = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    shared = read('app/templates/components/operational_alert_response.html')

    assert "summary = payload.get('summary')" in forecast
    assert "summary.get('highest_projected_percent', 0)" in forecast
    assert "horizon_days = safe_optional_int(payload.get('horizon_days')) or 90" in forecast
    assert 'review worker headroom.' in forecast
    assert "return 'Forecast snapshot loaded from analytics forecast service.'" in forecast
    assert 'CPU/memory consumer rows lack request or limit context.' in consumers
    assert 'Usage-only bars stay muted to avoid false risk signals.' in consumers
    for description in (
        'Verify the cluster, committed snapshot freshness, and alert-source evidence before acting.',
        'Assess severity and blast radius, identify affected workloads or namespaces, and assign an owner.',
        'Correlate labels, committed metrics, changes, dependencies, and signals to test the suspected cause.',
        'Confirm alert recovery, workload health, and SLI or capacity stability after the response.',
        'Record decisions, actions, verification results, and follow-up evidence for auditability.',
    ):
        assert description in response
    assert (
        "source_description='KAORI Alert Intelligence · Active AlertCase records and operational insights.'"
    ) in shared
    assert 'components/operational_alert_response.html' in response


def test_kubernetes_dashboard_reporting_domain_is_scoped_and_bounded() -> None:
    reporting = read('app/kubernetes/dashboard/sections/reporting.py')
    service = read('app/kubernetes/dashboard/service.py')
    standard = read('docs/design/patterns/OPERATIONAL_DASHBOARD.md')

    assert '_kubernetes_report_query(selected_cluster_id)' in reporting
    assert "Report.report_domain == 'kubernetes'" in reporting
    assert "ReportSchedule.report_domain == 'kubernetes'" in reporting
    assert "ReportTemplate.report_domain == 'kubernetes'" in reporting
    assert 'Report.cluster_id == selected_cluster_id' in reporting
    assert 'ReportSchedule.cluster_id == selected_cluster_id' in reporting
    assert '.order_by(Report.created_at.desc(), Report.id.desc())' in reporting
    assert '.limit(4)' in reporting
    assert 'count_kubernetes_reports(selected_cluster_id)' in service
    assert 'count_records(Report, selected_cluster_id)' not in service
    assert 'at most **four** latest generated report records' in standard
