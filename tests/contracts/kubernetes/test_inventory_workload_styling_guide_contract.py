from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_workload_page_uses_inventory_resource_pattern_components() -> None:
    hero = _read('app/templates/inventory/workloads/partials/_hero.html')
    posture = _read('app/templates/inventory/workloads/partials/_summary_cards.html')
    table = _read('app/templates/inventory/workloads/partials/_table_card.html')

    assert 'page_hero.context_card(' in hero
    assert 'inventory.posture_label' in hero
    assert 'resource_posture_grid.html' in posture
    assert 'operational_section_card.html' in posture
    assert 'table_ui.inventory_block_header(' in table
    assert 'table_ui.filter_select_classes()' in table
    assert 'table_ui.search_field(' in table


def test_workload_backend_owns_state_delivery_and_grouped_summary() -> None:
    source = _read('app/inventory/resources/workloads.py')

    assert '_OPERATIONAL_STATES' in source
    assert "'running': ('Stable', 'normal')" in source
    assert "'suspended': ('Suspended', 'info')" in source
    assert 'func.count(WorkloadInventory.id)' in source
    assert '.group_by(WorkloadInventory.workload_type, WorkloadInventory.status)' in source
    assert '.limit(8).all()' in source
    assert 'related_pod_count = related_query.count()' in source
    assert 'No associated Pods are represented' in source


def test_workload_status_filter_depends_on_workload_type() -> None:
    route = _read('app/inventory/routes.py')
    service = _read('app/inventory/resources/workloads.py')

    assert 'workload_type=workload_type' in route
    assert 'def get_workload_filter_statuses(' in service
    assert 'workload_type: str | None = None' in service
    assert 'WorkloadInventory.workload_type == workload_type' in service


def test_related_resource_collection_has_shared_owner() -> None:
    component = _read('app/templates/components/related_resource_collection.html')
    assert 'No Related Resources' in component
    assert 'status_indicator_label' in component
    assert 'Showing the first' in component
    assert 'action_href' in component
