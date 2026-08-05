from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_node_inventory_preserves_committed_evidence_and_missing_capacity() -> None:
    backend = read('app/inventory/resources/nodes.py')

    assert 'filter_current_generation(query, NodeInventory)' in backend
    assert "'total_cpu_display'" in backend
    assert "'cpu_coverage_description'" in backend
    assert "'memory_coverage_description'" in backend
    assert "'ephemeral_coverage_description'" in backend
    assert 'sum(cpu or 0' not in backend


def test_node_hero_uses_operational_fleet_posture() -> None:
    hero = read('app/templates/inventory/nodes/partials/_hero.html')
    backend = read('app/inventory/resources/nodes.py')

    assert 'inventory.fleet_posture_label' in hero
    assert 'inventory.fleet_posture_tone' in hero
    assert "'Active Signals', inventory.active_signal_nodes" in hero
    assert 'not_ready_nodes > 0 or network_issue_nodes > 0' in backend
    assert 'pressure_nodes > 0 or cordoned_nodes > 0' in backend


def test_node_filters_are_human_readable_and_accessible() -> None:
    routes = read('app/inventory/routes.py')
    backend = read('app/inventory/resources/nodes.py')
    table = read('app/templates/inventory/nodes/partials/_table_card.html')
    shared_table = read('app/templates/components/table.html')

    assert "_canonical_role_filter(value): _role_display(value)" in backend
    assert "func.lower(NodeInventory.role).in_(('control-plane', 'master'))" in backend
    assert "'value': value, 'label': _status_display(value)" in backend
    assert "valid_roles = {option['value'] for option in node_roles}" in routes
    assert 'for="nodes-cluster-filter"' in table
    assert 'for="nodes-role-filter"' in table
    assert 'for="nodes-status-filter"' in table
    assert 'for="nodes-search"' in table
    assert 'aria-label="Node inventory filters"' in table
    assert '{% macro search_field(name, value, placeholder, id=None)' in shared_table


def test_node_filters_refresh_the_complete_scope_workspace() -> None:
    table = read('app/templates/inventory/nodes/partials/_table_card.html')
    workspace = read('app/templates/inventory/nodes/partials/_page_workspace.html')
    routes = read('app/inventory/routes.py')

    assert 'hx-target="#nodes-page-workspace"' in table
    assert 'name="partial_mode" value="page_workspace"' in table
    assert 'id="nodes-page-workspace"' in workspace
    assert 'inventory/components/_data_freshness.html' in workspace
    assert "partial_mode == 'page_workspace'" in routes


def test_node_table_keeps_seven_columns_and_surfaces_conditions() -> None:
    content = read('app/templates/inventory/nodes/partials/_table_content.html')

    for header in ('Node', 'Cluster', 'Readiness', 'Role', 'Capacity', 'Network', 'Details'):
        assert f'>{header}<' in content
    assert '<caption class="sr-only">' in content
    assert content.count('scope="col"') == 7
    assert 'node.condition_summary' in content
    assert "technical_value.render(node.internal_ip or 'Not Reported')" in content


def test_node_detail_reuses_shared_metadata_and_avoids_duplicate_badges() -> None:
    detail = read('app/templates/inventory/nodes/partials/_node_detail_content.html')

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'components/technical_metadata_collection.html' in detail
    assert "detail.detail_row('Network Scope', node.network_scope)" in detail
    assert 'node.role_description' in detail
    assert "detail.detail_row('Scheduled Pods'" not in detail
    assert "table_label.metadata_label(taint, 'tag'" not in detail
    assert "detail.detail_card('Node Identity', 'badge-info', node.age" not in detail
    assert 'Committed Snapshot Boundary' in detail
    assert 'node.capacity_summary' in detail
    assert "node.scheduling_display == 'Not Reported'" in detail


def test_node_collection_preserves_incomplete_evidence() -> None:
    persistence = read('app/inventory/persistence.py')
    save_nodes = persistence[persistence.index('def save_nodes'):persistence.index('def _namespace_count_snapshot')]

    assert 'if metadata is None or not metadata.name' in save_nodes
    assert 'if status is None:' not in save_nodes
    assert "getattr(node_info, 'container_runtime_version', None)" in save_nodes


def test_node_inventory_standard_is_documented_and_gated() -> None:
    standard = read('docs/design/patterns/KUBERNETES_NODE_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_NODE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    assert 'Kubernetes Node Inventory Standard' in standard
    assert 'missing values are not converted to zero' in standard
    assert 'Fleet posture represented readiness only' in audit
    assert 'verify_node_inventory_standard.py' in quality_gate
