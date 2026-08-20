from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_context_reuses_snapshot_summary_metric_hierarchy() -> None:
    inventory = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html')

    context = inventory.split("'Inventory Context',", 1)[1].split("'Inventory Breakdown',", 1)[0]
    assert "side_drawer.metric('Environment'" in context
    assert "side_drawer.metric('Kubernetes Version'" in context
    assert "side_drawer.metric('Registered Cluster'" in context
    assert "side_drawer.metric('Last Collected'" in context
    assert "side_drawer.metric('Freshness Window'" in context
    assert "side_drawer.metric('Snapshot Source'" in context
    assert context.count("variant='plain'") >= 6
    assert 'detail_row(' not in context
    assert 'nowrap=True' not in inventory
    assert "'Cluster Identity'" not in inventory
    assert "'Snapshot Context'" not in inventory


def test_kubernetes_dashboard_forecast_schema_matches_latest_daily_average_payload() -> None:
    schema = read('app/kubernetes/dashboard/schema.py')
    builder = read('app/kubernetes/dashboard/sections/forecast.py')
    template = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')

    forecast_item = schema.split('class ForecastItem:', 1)[1].split('@dataclass', 1)[0]
    assert 'latest_daily_average_percent: float | None = None' in forecast_item
    assert 'current_percent:' not in forecast_item
    assert 'latest_daily_average_percent=current' in builder
    assert 'item.latest_daily_average_percent' in template
