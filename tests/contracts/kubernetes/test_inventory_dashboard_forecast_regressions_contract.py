from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_context_uses_quieter_metadata_hierarchy_than_snapshot_kpis() -> None:
    inventory = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html')

    context = inventory.split("'Inventory Context',", 1)[1].split("'Inventory Breakdown',", 1)[0]
    assert "side_drawer.context_fact('Environment'" in context
    assert "side_drawer.context_fact('Kubernetes Version'" in context
    assert "side_drawer.context_fact('Registered Cluster'" in context
    assert "side_drawer.context_fact('Last Collected'" in context
    assert "side_drawer.context_fact('Freshness Window'" in context
    assert "side_drawer.context_fact('Snapshot Source'" in context
    assert context.count('side_drawer.context_fact(') == 6
    assert 'detail_row(' not in context
    assert 'nowrap=True' not in inventory
    assert "'Cluster Identity'" not in inventory
    assert "'Snapshot Context'" not in inventory
    drawer = read('app/templates/components/side_drawer.html')
    context_macro = drawer.split('{% macro context_fact(', 1)[1].split('{%- endmacro %}', 1)[0]
    assert 'text-sm font-semibold leading-5 text-content-primary' in context_macro
    assert 'text-base font-semibold' not in context_macro


def test_kubernetes_dashboard_forecast_schema_matches_latest_daily_average_payload() -> None:
    schema = read('app/kubernetes/dashboard/schema.py')
    builder = read('app/kubernetes/dashboard/sections/forecast.py')
    template = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')

    forecast_item = schema.split('class ForecastItem:', 1)[1].split('@dataclass', 1)[0]
    assert 'latest_daily_average_percent: float | None = None' in forecast_item
    assert 'current_percent:' not in forecast_item
    assert 'latest_daily_average_percent=current' in builder
    assert 'item.latest_daily_average_percent' in template
