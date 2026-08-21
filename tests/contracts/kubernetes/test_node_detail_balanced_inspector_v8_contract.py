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
    assert 'data-kaori-node-inspector-flow="natural-content"' in node
    assert 'xl:grid-cols-12' in node
    assert 'macro inspector_panel(' in shared
    assert 'macro inspector_row(' in shared
    assert 'macro inspector_technical_row(' in shared
    assert 'macro inspector_summary_strip(' in shared


def test_node_v8_allocates_width_by_expected_content_length() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "detail.inspector_panel('Identity & Snapshot', 'badge-info')" in node
    assert "detail.inspector_panel('Node Capacity', 'gauge', 'xl:col-span-4')" in node
    assert "detail.inspector_panel('Connectivity & Network', 'network', 'xl:col-span-8'" in node
    assert "detail.inspector_panel('Runtime & Platform', 'terminal-square')" in node
    assert "detail.inspector_panel('Scheduling & Conditions', 'shield-check'" in node
    assert 'xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]' in node


def test_node_v8_long_values_use_natural_wrapping_without_nested_scroll() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'overflow-x-auto' not in node
    assert 'overflow-y-auto' not in node
    assert "detail.inspector_technical_row('System UUID', node.system_uuid, nowrap=false)" in node
    assert (
        "detail.inspector_technical_row('Hostname / FQDN', node.hostname_address or 'Not Reported', nowrap=false)"
        in node
    )
    assert "detail.inspector_technical_row('Kernel Version', node.kernel_version, nowrap=false)" in node
    assert (
        "detail.inspector_technical_row('Container Runtime', node.container_runtime_identifier, nowrap=false)" in node
    )
    assert 'break_all=not nowrap' in shared
    assert 'nowrap_values=false' in node
    assert 'wide_pairs=true' in node
    assert 'compact_pairs=false' in node


def test_node_v8_uses_semantic_status_and_violet_metadata_tags() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "metadata_label(node.cluster_name, 'building-2', true, 'detail')" in node
    assert "special_label(node.role_display, 'maintenance', 'shield', 'detail')" in node
    assert 'status_indicator_label(node.status_display, node_status_tone' in node
    assert "special_label(node.taints|length ~ ' '" in node


def test_node_v8_preserves_snapshot_and_operational_boundaries() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "operational_callout.render('Committed Snapshot Boundary'" in node
    assert 'operational_callout.render(node.operational_context.title' in node
    assert 'does not query the Kubernetes API live' in node
