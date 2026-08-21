from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_node_detail_uses_editorial_inspector_layout_with_natural_height_sections() -> None:
    detail = _read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = _read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'data-kaori-detail-density="editorial-inspector"' in detail
    assert 'data-kaori-inventory-detail-layout="editorial-technical-inspector"' in detail
    assert 'data-kaori-node-inspector' in detail
    assert 'data-kaori-node-inspector-layout="content-length-aware"' in detail
    assert 'xl:grid-cols-12' in detail
    assert 'macro inspector_section(' in shared
    assert 'macro inspector_fact(' in shared
    assert 'macro inspector_state_fact(' in shared

    assert 'min-h-80' not in detail
    assert 'min-h-96' not in detail

    for title in ('Identity & Snapshot', 'Capacity', 'Network Identity', 'Runtime & Platform', 'Scheduling & Conditions'):
        assert f"detail.inspector_section('{title}'" in detail

    assert "operational_callout.render('Committed Snapshot Boundary'" in detail
    assert 'operational_callout.render(node.operational_context.title' in detail
