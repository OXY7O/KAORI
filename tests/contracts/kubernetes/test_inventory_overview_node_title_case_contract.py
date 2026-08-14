from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_inventory_overview_uses_sentence_case_for_supporting_copy() -> None:
    content = _read('app/templates/inventory/kubernetes/overview/partials/_kpi_cards.html')
    backend = _read('app/inventory/kubernetes/overview.py')

    assert 'Open one Kubernetes asset inventory to review the objects collected' in content
    expected_descriptions = (
        'Worker and control-plane capacity.',
        'Tenant and application scopes.',
        'Deployments and workload controllers.',
        'Current runtime workload instances.',
        'Cluster networking endpoints.',
        'Published application entry points.',
        'Storage classes, volumes, and claims.',
        'ConfigMaps and Secret metadata.',
    )
    for description in expected_descriptions:
        assert description in backend


def test_node_inventory_supporting_copy_uses_sentence_case_and_footer_resource_case() -> None:
    summary = _read('app/templates/inventory/kubernetes/nodes/partials/_summary_cards.html')
    table = _read('app/templates/inventory/kubernetes/nodes/partials/_table_content.html')

    expected = (
        'inventory.cpu_coverage_description',
        'inventory.memory_coverage_description',
        'inventory.ephemeral_coverage_description',
        'Nodes excluded from new workload scheduling.',
        'Nodes reporting memory, disk, or PID pressure.',
        'Nodes reporting an unavailable network condition.',
    )
    for description in expected:
        assert description in summary

    assert "pagination_ui.resource_name('Nodes', pagination.total_items)" in table
    assert "pagination_ui.resource_name('nodes', pagination.total_items)" not in table
