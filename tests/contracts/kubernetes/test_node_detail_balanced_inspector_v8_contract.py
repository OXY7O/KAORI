from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_node_v9_uses_editorial_technical_information_architecture() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-inventory-detail="v9"' in node
    assert 'data-kaori-inventory-detail-layout="editorial-technical-inspector"' in node
    assert 'data-kaori-detail-density="editorial-inspector"' in node
    assert 'data-kaori-node-inspector-layout="content-length-aware"' in node
    assert 'macro inspector_section(' in shared
    assert 'macro inspector_fact(' in shared
    assert 'macro inspector_state_fact(' in shared
    assert 'macro inspector_summary_strip(' in shared


def test_node_v9_allocates_space_by_expected_value_length() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "detail.inspector_section('Identity & Snapshot'" in node
    assert "detail.inspector_section('Capacity'" in node
    assert "detail.inspector_section('Network Identity'" in node
    assert "detail.inspector_section('Runtime & Platform'" in node
    assert "detail.inspector_section('Scheduling & Conditions'" in node
    assert "'xl:col-span-4'" in node
    assert "'xl:col-span-8'" in node
    assert "class_name='sm:col-span-2'" in node
    assert 'lg:grid-cols-5' in node


def test_node_v9_keeps_predictably_long_values_on_one_line() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'overflow-x-auto whitespace-nowrap' in shared
    assert "detail.inspector_fact('System UUID', node.system_uuid, technical=true, monospace=true, nowrap=true" in node
    assert "detail.inspector_fact('Hostname / FQDN', node.hostname_address or 'Not Reported', technical=true, monospace=true, nowrap=true" in node
    assert "detail.inspector_fact('Kernel Version', node.kernel_version, technical=true, monospace=true, nowrap=true" in node
    assert "detail.inspector_fact('Container Runtime', node.container_runtime_identifier, technical=true, monospace=true, nowrap=true" in node
    assert 'nowrap_values=true' in node
    assert 'stacked_pairs=true' in node
    assert "'overflow-x-auto whitespace-nowrap' if nowrap_values" in metadata


def test_node_v9_uses_selective_monospace_without_turning_the_modal_into_code() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'monospace=true' in node
    assert 'font-mono' not in node
    assert 'monospace=monospace' in shared
    assert 'font-mono text-xs font-medium' in metadata
    assert 'text-sm font-semibold leading-5 text-content-primary' in shared


def test_node_v9_preserves_snapshot_and_operational_boundaries() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "operational_callout.render('Committed Snapshot Boundary'" in node
    assert 'operational_callout.render(node.operational_context.title' in node
    assert 'does not query the Kubernetes API live' in node
    assert "extra_classes='xl:col-span-5'" in node
    assert "extra_classes='xl:col-span-7'" in node
