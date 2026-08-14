from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_snapshot_source_uses_aligned_detail_row_for_canonical_value() -> None:
    details = read('app/templates/components/details/_detail_content.html')
    inventory = read('app/templates/inventory/kubernetes/overview/partials/_resources_by_cluster_content.html')

    assert 'macro detail_row(' in details
    assert 'whitespace-nowrap' in details
    assert "detail_row('Snapshot Source', cluster.snapshot_source, nowrap=True)" in inventory


def test_kubernetes_dashboard_forecast_schema_matches_latest_daily_average_payload() -> None:
    schema = read('app/dashboards/kubernetes/schema.py')
    builder = read('app/dashboards/kubernetes/sections/forecast.py')
    template = read('app/templates/dashboards/kubernetes/partials/_forecast_risk.html')

    forecast_item = schema.split('class ForecastItem:', 1)[1].split('@dataclass', 1)[0]
    assert 'latest_daily_average_percent: float | None = None' in forecast_item
    assert 'current_percent:' not in forecast_item
    assert 'latest_daily_average_percent=current' in builder
    assert 'item.latest_daily_average_percent' in template
