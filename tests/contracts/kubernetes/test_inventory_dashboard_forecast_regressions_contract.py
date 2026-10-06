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
