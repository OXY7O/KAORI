from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_node_v10_uses_unified_resource_sheet_information_architecture() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-inventory-detail="v10"' in node
    assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in node
    assert 'data-kaori-detail-density="unified-resource-sheet"' in node
    assert 'data-kaori-node-inspector' in node
    assert 'data-kaori-node-inspector-flow="natural-content"' in node
    assert 'data-kaori-node-inspector-layout="single-scroll-resource-sheet"' in node
    assert 'data-kaori-node-resource-sheet' in node
    assert 'data-kaori-inspector-section-layout="resource-sheet-band"' in shared
    assert 'macro inspector_section(' in shared
    assert 'macro inspector_row(' in shared
    assert 'macro inspector_technical_row(' in shared
    assert 'macro inspector_state_item(' in shared


def test_node_v10_long_evidence_gets_full_width_when_it_needs_it() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "detail.inspector_section('Identity & Snapshot', 'badge-info'" in node
    assert "detail.inspector_section('Connectivity & Network', 'network'" in node
    assert "detail.inspector_section('Node Capacity', 'gauge'" in node
    assert "detail.inspector_section('Runtime & Platform', 'terminal-square'" in node
    assert "detail.inspector_section('Scheduling & Conditions', 'shield-check'" in node
    assert (
        "detail.inspector_technical_row('Node Name', node.node_name, nowrap=true, class_name='lg:col-span-2')" in node
    )
    assert (
        "detail.inspector_technical_row('System UUID', node.system_uuid, nowrap=true, class_name='lg:col-span-2')"
        in node
    )
    assert (
        "detail.inspector_technical_row('Hostname / FQDN', node.hostname_address or 'Not Reported', "
        "nowrap=true, class_name='lg:col-span-2')" in node
    )
    assert "detail.inspector_row('OS Image', node.os_image, nowrap=true)" in node
    assert "detail.inspector_technical_row('Kernel Version', node.kernel_version, nowrap=true)" in node


def test_node_v10_uses_one_body_typeface_without_nested_scroll() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'overflow-x-auto' not in node
    assert 'overflow-y-auto' not in node
    assert 'overflow-y-auto' not in metadata
    assert 'monospace=false' in shared
    assert "table_label.status_label(taint_effect, taint_effect_tone, none, 'detail')" in node
    assert 'font-mono' not in node
    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert 'data-kaori-inventory-metadata-layout="resource-sheet-band"' in metadata
    assert 'sm:grid-cols-[minmax(26rem,0.42fr)_minmax(0,1fr)]' in metadata
    assert 'embedded=true' in node


def test_node_v10_header_keeps_context_quiet_and_copy_free() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert 'detail.header_identity_row()' in node
    assert '>Cluster<' in node
    assert '>Role<' in node
    assert '>Environment<' in node
    assert '>Status<' in node
    assert 'status_dot_classes' in node
    assert 'clipboard' not in node
    assert 'copy' not in node.lower()


def test_node_v10_preserves_snapshot_and_operational_boundaries() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "operational_callout.render('Committed Snapshot Boundary'" in node
    assert 'operational_callout.render(node.operational_context.title' in node
    assert 'does not query the Kubernetes API live' in node
    assert "extra_classes='xl:col-span-5'" in node
    assert "extra_classes='xl:col-span-7'" in node


def test_node_v10_taints_use_semantic_effect_labels() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert 'taint_effect_tone' in node
    assert "table_label.status_label(taint_effect, taint_effect_tone, none, 'detail')" in node
    assert 'technical_value.render(taint, break_all=false' not in node
