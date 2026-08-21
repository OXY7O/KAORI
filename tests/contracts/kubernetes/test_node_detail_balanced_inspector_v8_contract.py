from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_node_v9_uses_editorial_evidence_grid_information_architecture() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-inventory-detail="v9"' in node
    assert 'data-kaori-inventory-detail-layout="editorial-evidence-grid"' in node
    assert 'data-kaori-node-inspector' in node
    assert 'data-kaori-node-inspector-flow="natural-content"' in node
    assert 'data-kaori-node-inspector-layout="single-scroll-evidence-grid"' in node
    assert 'xl:grid-cols-12' in node
    assert 'macro inspector_section(' in shared
    assert 'macro inspector_row(' in shared
    assert 'macro inspector_technical_row(' in shared
    assert 'macro inspector_state_item(' in shared


def test_node_v9_allocates_width_by_expected_content_length() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "detail.inspector_section('Identity & Snapshot', 'badge-info'" in node
    assert "detail.inspector_section('Connectivity & Network', 'network'" in node
    assert "detail.inspector_section('Node Capacity', 'gauge'" in node
    assert "detail.inspector_section('Runtime & Platform', 'terminal-square'" in node
    assert "detail.inspector_section('Scheduling & Conditions', 'shield-check'" in node
    for span in ('xl:col-span-3', 'xl:col-span-4', 'xl:col-span-5', 'xl:col-span-7'):
        assert span in node
    assert 'lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]' in node


def test_node_v9_long_values_use_natural_wrapping_without_nested_scroll() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'overflow-x-auto' not in node
    assert 'overflow-y-auto' not in node
    assert "detail.inspector_technical_row('Node Name', node.node_name, nowrap=false)" in node
    assert "detail.inspector_technical_row('System UUID', node.system_uuid, nowrap=false)" in node
    assert (
        "detail.inspector_technical_row('Hostname / FQDN', node.hostname_address or 'Not Reported', nowrap=false)"
        in node
    )
    assert "detail.inspector_technical_row('Kernel Version', node.kernel_version, nowrap=false)" in node
    assert (
        "detail.inspector_technical_row('Container Runtime', node.container_runtime_identifier, nowrap=false)"
        in node
    )
    assert 'break_all=false' in shared
    assert 'overflow-y-auto' not in metadata
    assert 'nowrap_values=false' in node
    assert 'wide_pairs=true' in node
    assert 'compact_pairs=true' in node


def test_node_v9_header_preserves_context_without_copy_actions() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert 'detail.header_identity_row()' in node
    assert '>Cluster<' in node
    assert '>Role<' in node
    assert '>Environment<' in node
    assert '>Status<' in node
    assert 'status_indicator_label(node.status_display, node_status_tone' in node
    assert 'clipboard' not in node
    assert 'copy' not in node.lower()


def test_node_v9_preserves_snapshot_and_operational_boundaries() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "operational_callout.render('Committed Snapshot Boundary'" in node
    assert 'operational_callout.render(node.operational_context.title' in node
    assert 'does not query the Kubernetes API live' in node
    assert "extra_classes='xl:col-span-5'" in node
    assert "extra_classes='xl:col-span-7'" in node
