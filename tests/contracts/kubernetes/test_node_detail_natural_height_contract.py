from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_node_detail_uses_natural_height_full_width_horizontal_sections() -> None:
    detail = _read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = _read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'data-kaori-inventory-detail-layout="horizontal-section-stack"' in detail
    assert 'grid items-start gap-x-10 gap-y-8 p-5 sm:p-6 xl:grid-cols-2' not in detail
    assert 'macro inventory_section(' in shared
    assert 'data-kaori-inventory-detail-section' in shared

    # Natural-height sections avoid blank equal-height card space.
    assert 'min-h-80' not in detail
    assert 'min-h-96' not in detail

    assert "detail.inventory_section('Node Identity'" in detail
    assert "detail.inventory_section('Node Capacity'" in detail
    assert "detail.inventory_section('Connectivity'" in detail
    assert "detail.inventory_section('Platform & Runtime'" in detail
    assert "detail.inventory_section('Scheduling & Conditions'" in detail
    assert 'operational_callout.render(node.operational_context.title' in detail
