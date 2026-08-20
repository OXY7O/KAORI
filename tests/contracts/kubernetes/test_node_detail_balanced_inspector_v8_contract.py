from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_node_v8_uses_balanced_inspector_information_architecture() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-inventory-detail="v8"' in node
    assert 'data-kaori-inventory-detail-layout="balanced-inspector"' in node
    assert 'data-kaori-node-inspector' in node
    assert 'lg:grid-cols-[13.5rem_minmax(0,1fr)]' in node
    assert 'xl:grid-cols-12' in node
    assert 'macro inspector_panel(' in shared
    assert 'macro inspector_row(' in shared
    assert 'macro inspector_technical_row(' in shared
    assert 'macro inspector_rail_item(' in shared
    assert 'macro inspector_summary_strip(' in shared


def test_node_v8_allocates_width_by_expected_content_length() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "detail.inspector_panel('Identity', 'badge-info', 'xl:col-span-5')" in node
    assert "detail.inspector_panel('Node Capacity', 'gauge', 'xl:col-span-3')" in node
    assert "detail.inspector_panel('Connectivity', 'network', 'xl:col-span-4'" in node
    assert "detail.inspector_panel('Runtime & Platform', 'terminal-square', 'xl:col-span-7')" in node
    assert "detail.inspector_panel('Scheduling & Conditions', 'shield-check', 'xl:col-span-5'" in node


def test_node_v8_keeps_predictably_long_values_on_one_line() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'overflow-x-auto whitespace-nowrap' in shared
    assert "detail.inspector_technical_row('System UUID', node.system_uuid)" in node
    assert "detail.inspector_technical_row('Hostname / FQDN', node.hostname_address or 'Not Reported')" in node
    assert "detail.inspector_technical_row('Kernel Version', node.kernel_version, nowrap=true)" in node
    assert "detail.inspector_technical_row('Container Runtime', node.container_runtime_identifier, nowrap=true)" in node
    assert 'nowrap_values=true' in node
    assert "'overflow-x-auto whitespace-nowrap' if nowrap_values" in metadata


def test_node_v8_uses_semantic_status_and_violet_metadata_tags() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "special_label(node.cluster_name, 'maintenance', 'building-2', 'detail')" in node
    assert "special_label(node.role_display, 'maintenance', 'shield', 'detail')" in node
    assert 'status_indicator_label(node.status_display, node_status_tone' in node
    assert "special_label(node.taints|length ~ ' '" in node


def test_node_v8_preserves_snapshot_and_operational_boundaries() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "operational_callout.render('Committed Snapshot Boundary'" in node
    assert 'operational_callout.render(node.operational_context.title' in node
    assert 'does not query the Kubernetes API live' in node
