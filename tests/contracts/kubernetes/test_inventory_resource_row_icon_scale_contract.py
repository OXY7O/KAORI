from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COMPACT_RESOURCE_TABLES = (
    'namespaces',
    'workloads',
    'pods',
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
    assert 'node.hostname_address' in content


def test_workload_resource_cell_keeps_compact_icon_and_plain_state_text() -> None:
    content = _table('workloads')

    assert 'data-lucide="boxes"' in content
    assert 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md' in content
    assert '{{ workload.state_display }}' in content
    assert "status_label(workload.state_display" not in content
