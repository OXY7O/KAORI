from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COMPACT_RESOURCE_TABLES = (
    'namespaces',
    'services',
    'ingresses',
    'storage',
    'configuration',
)


def _table(resource: str) -> str:
    return (
        ROOT
        / 'app'
        / 'templates'
        / 'inventory'
        / resource
        / 'partials'
        / '_table_content.html'
    ).read_text(encoding='utf-8')


def test_single_line_inventory_resource_cells_use_compact_icon_container() -> None:
    compact = 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md'
    oversized = 'flex h-8 w-8 shrink-0 items-center justify-center rounded-md'

    for resource in COMPACT_RESOURCE_TABLES:
        content = _table(resource)
        assert compact in content, resource
        assert oversized not in content, resource


def test_node_resource_cell_keeps_two_line_icon_container() -> None:
    content = _table('nodes')

    assert 'flex h-8 w-8 shrink-0 items-center justify-center rounded-md' in content
    assert 'node.node_name' in content
    assert 'node.internal_ip' in content
    assert 'node.hostname_address' not in content


def test_workload_resource_cell_uses_text_only_identity_and_plain_state() -> None:
    content = _table('workloads')

    assert 'data-lucide="boxes"' not in content
    assert 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md' not in content
    assert '{{ workload.state_display }}' in content
    assert "status_label(workload.state_display" not in content
    assert '{{ workload.type }}' in content
    assert '{{ workload.update_strategy }}' in content


def test_pod_resource_cell_uses_text_only_identity_and_semantic_phase() -> None:
    content = _table('pods')

    assert 'data-lucide="package"' not in content
    assert 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md' not in content
    assert "metadata_label(pod.namespace" not in content
    assert "status_label(pod.status or 'Unknown', phase_tone)" in content
    assert 'phase_icon' not in content
    assert 'ready_icon' not in content
    assert 'restart_tone' in content
