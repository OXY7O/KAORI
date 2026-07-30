from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
NAMESPACED_RESOURCE_TABLES = (
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


def test_namespaced_inventory_tables_use_shared_namespace_identity() -> None:
    shared_table = (ROOT / 'app/templates/components/table.html').read_text(encoding='utf-8')

    assert "macro namespace_identity(name, class_name='max-w-[220px]')" in shared_table
    assert 'data-lucide="folder-tree"' in shared_table
    assert 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md' in shared_table
    assert 'font-semibold leading-5 text-content-primary' in shared_table

    for resource in NAMESPACED_RESOURCE_TABLES:
        content = _table(resource)
        if resource in {'workloads', 'pods'}:
            assert 'table_ui.namespaced_scope_identity(' in content
        else:
            assert 'table_ui.namespace_identity(' in content, resource


def test_node_resource_cell_uses_shared_two_line_identity_and_technical_network_value() -> None:
    content = _table('nodes')
    shared_table = (ROOT / 'app/templates/components/table.html').read_text(encoding='utf-8')

    assert "table_ui.title_cell(node.node_name, node.identity_supporting, 'server')" in content
    assert 'components/technical_value.html' in content
    assert 'technical_value.render(node.internal_ip)' in content
    assert 'node.hostname_address' not in content
    assert "{{ 'h-10 w-10' if supporting_text else 'h-8 w-8' }}" in shared_table


def test_workload_resource_cell_uses_namespaced_scope_and_operational_state() -> None:
    content = _table('workloads')

    assert 'table_ui.namespaced_scope_identity(' in content
    assert "table_ui.title_cell(workload.name, workload.identity_supporting, 'boxes')" in content
    assert 'table_label.status_indicator_label(workload.operational_state_label, workload.operational_state_tone)' in content
    assert '{{ workload.state_display }}' in content
    assert "status_label(workload.update_strategy" not in content
    assert '{{ workload.delivery_model }}' in content
    assert '{{ workload.runtime_primary }}' in content


def test_pod_resource_cell_uses_namespaced_scope_and_runtime_posture() -> None:
    content = _table('pods')

    assert 'table_ui.namespaced_scope_identity(' in content
    assert "table_ui.title_cell(pod.name, pod.identity_supporting, 'package')" in content
    assert 'table_label.status_indicator_label(pod.operational_state_label, pod.operational_state_tone)' in content
    assert '{{ pod.state_evidence }}' in content
    assert '{{ pod.owner_display }}' in content
    assert '{{ pod.activity_secondary }}' in content
    assert 'phase_tone' not in content
    assert 'restart_tone' not in content
