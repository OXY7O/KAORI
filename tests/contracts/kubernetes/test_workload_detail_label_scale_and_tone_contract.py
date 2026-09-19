from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_workload_detail_uses_full_workspace_modal_reference_structure() -> None:
    template = _read('app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html')

    assert 'data-kaori-detail-variant="full-workspace-modal"' in template
    assert "detail.inventory_section('Workload Identity'" in template
    assert "detail.inventory_section('Runtime State'" in template
    assert "detail.inventory_section('Pod Template'" in template
    assert 'data-kaori-detail-density="unified-resource-sheet"' in template
    assert 'xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]' not in template
    assert 'items-stretch' not in template
    assert template.count('stretch=false') >= 3
    assert 'min-h-80' not in template
    assert 'min-h-96' not in template
    assert 'min-h-[28rem]' not in template


def test_workload_configuration_is_factual_not_implicitly_scored() -> None:
    template = _read('app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html')

    assert 'table_label.status_label(container.pull_policy' not in template
    assert 'normalized_pull_policy' not in template
    assert "metadata_collection.render('Node Selectors'" in template
    assert "metadata_collection.render('Tolerations'" in template
    assert 'workload.delivery_rows' in template
    assert 'workload.placement_rows' in template


def test_workload_detail_uses_related_resources_metadata_and_context() -> None:
    template = _read('app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html')

    assert 'related_collection.inventory_render(' in template
    assert "'Associated Pods'" in template
    assert "'Open Pod Inventory'" in template
    assert "metadata_collection.render('Workload Labels'" in template
    assert "metadata_collection.render('Workload Annotations'" in template
    assert "operational_callout.render('Committed Snapshot Boundary'" in template
    assert 'workload.operational_context.title' in template
