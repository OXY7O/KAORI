from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    backend = read('app/inventory/kubernetes/resources/nodes.py')
    routes = read('app/inventory/kubernetes/routes.py')
    hero = read('app/templates/inventory/kubernetes/nodes/partials/_hero.html')
    summary = read('app/templates/inventory/kubernetes/nodes/partials/_summary_cards.html')
    table_card = read('app/templates/inventory/kubernetes/nodes/partials/_table_card.html')
    table_content = read('app/templates/inventory/kubernetes/nodes/partials/_table_content.html')
    detail = read('app/templates/inventory/kubernetes/nodes/partials/_node_detail_content.html')
    workspace = read('app/templates/inventory/kubernetes/nodes/partials/_page_workspace.html')
    persistence = read('app/inventory/kubernetes/persistence.py')
    formatting = read('app/inventory/kubernetes/formatting.py')
    table_component = read('app/templates/components/table.html')
    standard = read('docs/design/patterns/KUBERNETES_NODE_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_NODE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        'filter_current_generation(query, NodeInventory)' in backend,
        'Node list must use the committed generation.',
        errors,
    )
    require(
        'filter_current_generation(db.session.query(func.count(PodInventory.id)), PodInventory)' in backend,
        'Scheduled Pod counts must use the committed generation.',
        errors,
    )
    require(
        "'fleet_posture_tone': fleet_posture_tone" in backend, 'Fleet posture must be exposed by the backend.', errors
    )
    require(
        'not_ready_nodes > 0 or network_issue_nodes > 0 or pressure_nodes > 0 or cordoned_nodes > 0' in backend,
        'Fleet posture must include readiness, network, pressure, and scheduling signals.',
        errors,
    )
    require("'total_cpu_display'" in backend, 'CPU must expose an explicit display value.', errors)
    require("'cpu_coverage_description'" in backend, 'CPU coverage must remain explicit.', errors)
    require("'memory_coverage_description'" in backend, 'Memory coverage must remain explicit.', errors)
    require("'ephemeral_coverage_description'" in backend, 'Ephemeral-storage coverage must remain explicit.', errors)
    require('sum(cpu or 0' not in backend, 'Missing CPU evidence must not be silently converted to zero.', errors)
    require(
        '_canonical_role_filter(value): _role_display(value)' in backend,
        'Role filters must deduplicate legacy control-plane aliases.',
        errors,
    )
    require(
        "func.lower(NodeInventory.role).in_(('control-plane', 'master'))" in backend,
        'The canonical Control Plane filter must match legacy and current role values.',
        errors,
    )
    require(
        "'value': value, 'label': _status_display(value)" in backend,
        'Readiness filters must separate canonical value from display label.',
        errors,
    )
    require(
        "'title': 'Validate Node Readiness Evidence'" in backend,
        'Unknown readiness must produce explicit validation guidance.',
        errors,
    )
    require(
        "'title': 'Validate Node Scheduling Evidence'" in backend,
        'Unknown scheduling must not produce a healthy action.',
        errors,
    )
    require("row[3] != 'Ready'" in backend, 'Unknown readiness must count as an active signal.', errors)
    require(
        'if metadata is None or not metadata.name' in persistence,
        'Node collection must preserve named Nodes with incomplete status evidence.',
        errors,
    )
    require(
        'if status is None:'
        not in persistence[persistence.index('def save_nodes') : persistence.index('def _namespace_count_snapshot')],
        'Node collection must not discard Nodes solely because status is absent.',
        errors,
    )
    require(
        'caller owns final presentation rounding' in formatting,
        'Capacity aggregation must preserve precision until the fleet total is complete.',
        errors,
    )

    require(
        "valid_roles = {option['value'] for option in node_roles}" in routes,
        'Role validation must use canonical filter values.',
        errors,
    )
    require(
        "valid_statuses = {option['value'] for option in node_statuses}" in routes,
        'Status validation must use canonical filter values.',
        errors,
    )

    require('page_hero.context_card' in hero, 'Node Inventory must use the canonical Hero context card.', errors)
    require('inventory.fleet_posture_label' in hero, 'Hero status must use overall fleet posture.', errors)
    require(
        "'Active Signals', inventory.active_signal_nodes" in hero, 'Hero context must expose active signals.', errors
    )
    require('id="nodes-page-workspace"' in workspace, 'Node filtering must own a complete page workspace.', errors)
    require(
        'inventory/kubernetes/components/_data_freshness.html' in workspace,
        'The workspace must refresh snapshot context with filtered scope.',
        errors,
    )
    require(
        'hx-target="#nodes-page-workspace"' in table_card,
        'Node filters must refresh Hero, snapshot, posture, and table together.',
        errors,
    )
    require(
        'name="partial_mode" value="page_workspace"' in table_card,
        'Node filter requests must select the page-workspace partial.',
        errors,
    )

    for token in (
        'inventory.total_cpu_display',
        'inventory.cpu_coverage_description',
        'inventory.total_memory_display',
        'inventory.memory_coverage_description',
        'inventory.total_ephemeral_storage_display',
        'inventory.ephemeral_coverage_description',
        'Nodes with Pressure',
    ):
        require(token in summary, f'Missing Node Resource Posture contract: {token}', errors)

    for token in (
        'for="nodes-cluster-filter"',
        'for="nodes-role-filter"',
        'for="nodes-status-filter"',
        'for="nodes-search"',
        'aria-label="Node inventory filters"',
        'Latest committed Kubernetes node records',
        'role_option.label',
        'status_option.label',
    ):
        require(token in table_card, f'Missing filter/table-header contract: {token}', errors)

    require(
        '{% macro search_field(name, value, placeholder, id=None)' in table_component,
        'Shared search fields must support an accessible id.',
        errors,
    )

    for token in (
        '<caption class="sr-only">',
        'scope="col"',
        'node.condition_summary',
        "technical_value.render(node.internal_ip or 'Not Reported')",
        "pagination_ui.resource_name('Nodes', pagination.total_items)",
    ):
        require(token in table_content, f'Missing compact Node table contract: {token}', errors)

    for token in (
        'data-kaori-detail-density="adaptive-stacks"',
        'components/technical_metadata_collection.html',
        "detail.detail_card('Node Identity', 'badge-info')",
        "detail.detail_card('Node Capacity', 'gauge')",
        "detail.detail_row('Network Scope', node.network_scope)",
        'node.role_description',
        'No taints were reported in the current snapshot.',
        "'Node Labels'",
        'Committed Snapshot Boundary',
    ):
        require(token in detail, f'Missing Node detail contract: {token}', errors)

    require(
        "detail.detail_row('Scheduled Pods'" not in detail, 'Connectivity must not duplicate Scheduled Pods.', errors
    )
    require(
        "table_label.metadata_label(taint, 'tag'" not in detail, 'Taints must not use Violet metadata pills.', errors
    )
    require(
        "detail.detail_card('Node Identity', 'badge-info', node.age" not in detail,
        'Node Identity must not duplicate Age as a badge.',
        errors,
    )

    for token in (
        'Kubernetes Node Inventory Standard',
        'missing values are not converted to zero',
        'Node | Cluster | Readiness | Role | Capacity | Network | Details',
        'data-kaori-detail-density="adaptive-stacks"',
    ):
        require(token in standard, f'Node Inventory documentation is missing: {token}', errors)
    require(
        'Fleet posture represented readiness only' in audit,
        'The alignment audit must record the posture correction.',
        errors,
    )
    require(
        'verify_node_inventory_standard.py' in quality_gate,
        'The Node Inventory verifier must run in the static quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Node Inventory Standard audit passed: committed snapshot semantics, fleet posture, capacity coverage, compact table, detail workspace, accessibility, and documentation are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
