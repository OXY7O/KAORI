from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_node_detail_uses_balanced_inspector_layout_with_natural_height_sections() -> None:
    detail = _read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = _read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'data-kaori-detail-density="balanced-inspector"' in detail
    assert 'data-kaori-inventory-detail-layout="balanced-inspector"' in detail
    assert 'data-kaori-node-inspector' in detail
    assert 'data-kaori-node-inspector-flow="natural-content"' in detail
    assert 'xl:grid-cols-12' in detail
    assert 'macro inspector_panel(' in shared
    assert 'macro inspector_row(' in shared
    assert 'macro inspector_technical_row(' in shared

    assert 'min-h-80' not in detail
    assert 'min-h-96' not in detail
    assert 'overflow-x-auto' not in detail
    assert 'overflow-y-auto' not in detail

    for title in (
        'Identity & Snapshot',
        'Node Capacity',
        'Connectivity & Network',
        'Runtime & Platform',
        'Scheduling & Conditions',
    ):
        assert f"detail.inspector_panel('{title}'" in detail

    assert "operational_callout.render('Committed Snapshot Boundary'" in detail
    assert 'operational_callout.render(node.operational_context.title' in detail
