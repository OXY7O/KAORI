from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_snapshot_context_uses_stacked_rows_for_long_values() -> None:
    details = read('app/templates/components/details/_detail_content.html')
    inventory = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html')

    assert 'macro stacked_detail_row(' in details
    assert "detail_row('Snapshot Source', cluster.snapshot_source)" in inventory
    assert "detail_row('Last Collected'" in inventory
    assert 'nowrap=True' not in inventory


def test_kubernetes_dashboard_forecast_schema_matches_latest_daily_average_payload() -> None:
    schema = read('app/kubernetes/dashboard/schema.py')
    builder = read('app/kubernetes/dashboard/sections/forecast.py')
    template = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')

    forecast_item = schema.split('class ForecastItem:', 1)[1].split('@dataclass', 1)[0]
    assert 'latest_daily_average_percent: float | None = None' in forecast_item
    assert 'current_percent:' not in forecast_item
    assert 'latest_daily_average_percent=current' in builder
    assert 'item.latest_daily_average_percent' in template
