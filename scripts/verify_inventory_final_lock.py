#!/usr/bin/env python3
"""Verify the final Kubernetes Inventory release boundary and shared UI contract."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / 'app/kubernetes/inventory/routes.py'
RESOURCE_NAMES = ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')
READ_VIEWS = {
    'overview',
    'topology',
    'topology_data',
    'nodes',
    'node_details',
    'namespaces',
    'namespace_details',
    'configuration',
    'configuration_details',
    'workloads',
    'workload_details',
    'pods',
    'pod_details',
    'services',
    'service_details',
    'ingresses',
    'ingress_details',
    'storage',
    'storage_details',
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def called_name(decorator: ast.expr) -> str | None:
    called = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(called, ast.Name):
        return called.id
    if isinstance(called, ast.Attribute):
        return called.attr
    return None


def permission(function: ast.FunctionDef) -> str | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or called_name(decorator) != 'permission_required':
            continue
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            return str(decorator.args[0].value)
    return None


def main() -> int:
    errors: list[str] = []
    routes_source = ROUTES.read_text(encoding='utf-8')
    tree = ast.parse(routes_source, filename=str(ROUTES))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    require(
        '@inventory_bp.before_request' not in routes_source,
        'Inventory must not short-circuit AuthZ in before_request.',
        errors,
    )
    require(
        '_clusterless_inventory_htmx_guard' in routes_source,
        'Inventory must keep the authorized HTMX clusterless guard.',
        errors,
    )

    for name in sorted(READ_VIEWS):
        function = functions.get(name)
        require(function is not None, f'Inventory read view {name} is missing.', errors)
        if function is None:
            continue
        decorators = [called_name(decorator) for decorator in function.decorator_list]
        require(permission(function) == 'inventory.view', f'{name} must require inventory.view.', errors)
        require(
            '_clusterless_inventory_htmx_guard' in decorators,
            f'{name} must use the clusterless HTMX guard after authorization.',
            errors,
        )
        if 'permission_required' in decorators and '_clusterless_inventory_htmx_guard' in decorators:
            require(
                decorators.index('permission_required') < decorators.index('_clusterless_inventory_htmx_guard'),
                f'{name} decorator order must keep permission_required outside the clusterless guard.',
                errors,
            )

    sync = functions.get('sync')
    require(
        sync is not None and permission(sync) == 'clusters.sync',
        'Inventory sync must retain clusters.sync.',
        errors,
    )

    read_side = '\n'.join(
        [read('app/kubernetes/inventory/overview.py')]
        + [
            path.read_text(encoding='utf-8')
            for path in sorted((ROOT / 'app/kubernetes/inventory/resources').rglob('*.py'))
        ]
        + [
            path.read_text(encoding='utf-8')
            for path in sorted((ROOT / 'app/kubernetes/inventory/topology').rglob('*.py'))
        ]
    )
    for token in (
        'kubernetes.client',
        'get_integration(',
        'client.build',
        'requests.get(',
        'requests.post(',
        'httpx.',
        'urllib.request',
        'boto3.client',
        'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver',
    ):
        require(token not in read_side, f'Inventory read side must remain provider-free: {token}', errors)

    topology_repository = read('app/kubernetes/inventory/topology/repository.py')
    topology_builder = read('app/kubernetes/inventory/topology/node_builder.py')
    require(
        'joinedload(Cluster.kubernetes_connection)' in topology_repository,
        'Topology cluster identity must eager-load the canonical Kubernetes connection relationship.',
        errors,
    )
    require(
        'cluster.kubernetes_connection.server' in topology_builder,
        'Topology API Server presentation must use the loaded DB relationship.',
        errors,
    )

    formatting = read('app/kubernetes/inventory/formatting.py')
    common = read('app/kubernetes/inventory/resources/common.py')
    for retired in ('def format_byte_count(', 'def format_gib('):
        require(retired not in formatting, f'Retired Inventory helper must remain removed: {retired}', errors)
    require(
        'def _split_inventory_values(' not in common,
        'Retired Inventory split helper must remain removed.',
        errors,
    )
    require(
        not (ROOT / 'app/templates/inventory/partials/_README.md').exists(),
        'Stale empty Inventory template-folder README must remain removed.',
        errors,
    )

    require(
        "f'kubernetes/inventory/{resource}/index.html'" in routes_source
        and "f'kubernetes/inventory/{resource}/partials/_page_workspace.html'" in routes_source
        and "f'kubernetes/inventory/{resource}/partials/_table_card.html'" in routes_source
        and "f'kubernetes/inventory/{resource}/partials/_table_content.html'" in routes_source,
        'Inventory resource template registry must use the canonical inventory/kubernetes namespace.',
        errors,
    )
    require(
        "f'inventory/{resource}/index.html'" not in routes_source,
        'Inventory resource template registry must not use the retired root Inventory namespace.',
        errors,
    )
    storage_function = functions.get('storage')
    if storage_function is not None:
        storage_source = ast.get_source_segment(routes_source, storage_function) or ''
        require(
            "inventory['scope_label'] = _inventory_scope_label(clusters, cluster_id)" in storage_source,
            'Storage Inventory must populate the shared scope label used by its Hero.',
            errors,
        )

    overview_hero = read('app/templates/kubernetes/inventory/overview/partials/_hero.html')
    topology_hero = read('app/templates/kubernetes/inventory/topology/partials/_hero.html')
    blocked_hero = read('app/templates/components/cluster/_hero_blocked_context.html')
    require(
        "page_hero.context_metric('boxes', 'Connected Clusters', '0', 'No Kubernetes connection available')"
        in blocked_hero
        and "page_hero.context_metric('circle-dot-dashed', blocked_state_label, 'Blocked', 'Cluster access is required'"
        in blocked_hero,
        'Inventory must inherit the canonical Kubernetes setup-blocked Hero context.',
        errors,
    )
    require(
        'page_hero.context_card(' in overview_hero,
        'Inventory Overview must use canonical status-oriented Hero context.',
        errors,
    )
    require(
        'page_hero.context_status_badge(' in topology_hero,
        'Topology Hero must use the canonical Status Badge Box.',
        errors,
    )
    for page_name, hero_source in (('overview', overview_hero), ('topology', topology_hero)):
        require(
            'components/cluster/_hero_blocked_context.html' in hero_source and 'Inventory Readiness' in hero_source,
            f'{page_name} Hero must use the shared Kubernetes setup-blocked context.',
            errors,
        )
        require(
            'Committed Inventory' in hero_source and 'Cluster Setup Required' in hero_source,
            f'{page_name} Hero must replace blocked numeric metadata with setup-safe inventory metadata.',
            errors,
        )
    overview_page = read('app/templates/kubernetes/inventory/overview/index.html')
    overview_content = read('app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html')
    overview_detail = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    topology_page = read('app/templates/kubernetes/inventory/topology/index.html')
    for page_name, page_source in (('overview', overview_page), ('topology', topology_page)):
        blocker = page_source.find('{% if cluster_onboarding.is_blocked %}')
        blocker_else = page_source.find('{% else %}', blocker)
        snapshot = page_source.find('kubernetes/inventory/components/_data_freshness.html')
        require(
            blocker >= 0 and blocker < blocker_else < snapshot,
            f'{page_name} must hide Inventory Data Snapshot behind the onboarding blocker.',
            errors,
        )

    for token in (
        'resource_detail_modal.inventory_host(',
        "url_for('inventory.overview_cluster_details', cluster_id=0)",
    ):
        require(token in overview_page, f'Inventory Overview modal-host contract missing: {token}', errors)
    for token in (
        'resource_detail_modal.detail_button(',
        "url_for('inventory.overview_cluster_details', cluster_id=cluster.id)",
    ):
        require(token in overview_content, f'Inventory Overview detail-button contract missing: {token}', errors)
    for retired in ('components/side_drawer.html', 'side_drawer.render(', 'openDrawer'):
        require(retired not in overview_content, f'Inventory Overview retains retired inline drawer: {retired}', errors)
    for token in (
        'data-kaori-detail-density="unified-resource-sheet"',
        'data-kaori-inventory-detail="v10"',
        'data-kaori-inventory-detail-layout="unified-resource-sheet"',
        'detail.inspector_summary_strip(',
        'detail.resource_sheet()',
        'Cluster Identity',
        'Snapshot Context',
        'Inventory Breakdown',
        'Inventory Signals',
    ):
        require(token in overview_detail, f'Inventory Overview cluster detail V10 contract missing: {token}', errors)
    require(
        'def overview_cluster_details(' in routes_source and 'get_inventory_overview_cluster_detail' in routes_source,
        'Inventory Overview cluster detail route must use the committed overview read model.',
        errors,
    )


    detail_primitives = read('app/templates/components/details/_detail_content.html')
    require(
        "description=None" in detail_primitives
        and 'data-kaori-inventory-section-description' in detail_primitives
        and 'bg-surface-elevated/35' in detail_primitives
        and 'absolute inset-y-0 left-0 w-0.5 bg-kaori-primary/70' not in detail_primitives,
        'Shared Inventory resource-sheet bands must provide descriptive left rails without the deprecated Violet edge accent.',
        errors,
    )

    for resource in RESOURCE_NAMES:
        hero = read(f'app/templates/kubernetes/inventory/{resource}/partials/_hero.html')
        table = read(f'app/templates/kubernetes/inventory/{resource}/partials/_table_content.html')
        workspace = read(f'app/templates/kubernetes/inventory/{resource}/partials/_page_workspace.html')
        blocker = workspace.find('{% if cluster_onboarding.is_blocked %}')
        blocker_else = workspace.find('{% else %}', blocker)
        snapshot = workspace.find('kubernetes/inventory/components/_data_freshness.html')
        require(
            blocker >= 0 and blocker < blocker_else < snapshot,
            f'{resource} must hide Inventory Data Snapshot behind the onboarding blocker.',
            errors,
        )
        require(
            'page_hero.context_card(' in hero,
            f'{resource} Hero must use the canonical Status Badge Box context card.',
            errors,
        )
        require(
            'components/cluster/_hero_blocked_context.html' in hero and 'Inventory Readiness' in hero,
            f'{resource} Hero must use the shared Kubernetes setup-blocked context.',
            errors,
        )
        require(
            'Committed Inventory' in hero and 'Cluster Setup Required' in hero,
            f'{resource} Hero must replace blocked numeric metadata with setup-safe inventory metadata.',
            errors,
        )
        require('components/table.html' in table, f'{resource} must use the shared table component.', errors)
        require('components/pagination.html' in table, f'{resource} must use canonical pagination.', errors)
        require(
            'components/resource_detail_modal.html' in table,
            f'{resource} details must use the shared modal.',
            errors,
        )
        require('detail_button(' in table, f'{resource} table must expose canonical View Details action.', errors)
        detail_partial = {
            'nodes': '_node_detail_content.html',
            'namespaces': '_namespace_detail_content.html',
            'configuration': '_configuration_detail_content.html',
            'workloads': '_workload_detail_content.html',
            'pods': '_pod_detail_content.html',
            'services': '_service_detail_content.html',
            'ingresses': '_ingress_detail_content.html',
            'storage': '_storage_detail_content.html',
        }[resource]
        detail_source = read(f'app/templates/kubernetes/inventory/{resource}/partials/{detail_partial}')
        require(
            'data-kaori-detail-density="unified-resource-sheet"' in detail_source,
            f'{resource} detail must use Unified Resource Sheet density.',
            errors,
        )
        require(
            'data-kaori-inventory-detail="v10"' in detail_source,
            f'{resource} detail must declare Inventory detail V10.',
            errors,
        )
        require(
            'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail_source,
            f'{resource} detail must use the Unified Resource Sheet layout.',
            errors,
        )
        require(
            'detail.inspector_summary_strip(' in detail_source,
            f'{resource} detail must use the shared connected operational summary strip.',
            errors,
        )
        require(
            'data-kaori-unified-resource-sheet' in detail_source,
            f'{resource} detail must expose one unified evidence-sheet owner.',
            errors,
        )
        require(
            ('description=' in detail_source)
            if resource != 'nodes'
            else ('detail.inspector_section(' in detail_source),
            f'{resource} detail must explain evidence scope in the left resource-sheet rail.',
            errors,
        )
        require(
            'detail.header_identity_row()' in detail_source,
            f'{resource} detail header must group title, metadata, and primary state in one identity row.',
            errors,
        )
        require(
            'detail.header_badge_row()' not in detail_source,
            f'{resource} detail header must not render primary state below the supporting description.',
            errors,
        )
        require(
            'self-start sm:self-auto' not in detail_source,
            f'{resource} detail header must not detach state labels below the leading icon.',
            errors,
        )

    require(
        'macro header_identity_row()' in detail_primitives
        and 'data-resource-detail-header-identity' in detail_primitives
        and 'macro header_badge_row()' not in detail_primitives,
        'Shared detail primitives must own one grouped Inventory title/metadata/state identity row.',
        errors,
    )

    standard = read('docs/design/patterns/INVENTORY_RESOURCE_PAGE.md')
    audit = read('docs/design/audits/KUBERNETES_INVENTORY_FINAL_RECHECK_2026_08.md')
    require(
        '# Inventory Resource Page Pattern v1.3' in standard,
        'Inventory Resource Page standard must be v1.3.',
        errors,
    )
    for phrase in (
        'Authorization before blocker evaluation',
        'Status Badge Box',
        '5 / 10 / 25 / 50',
        'Full Workspace Modal',
    ):
        require(phrase in standard, f'Inventory standard must document {phrase}.', errors)
    require(
        'Final Recheck' in audit and 'L0–L7' in audit,
        'Inventory final audit must document layered release evidence.',
        errors,
    )

    quality_gate = read('scripts/quality_gate.sh')
    core_lock = read('scripts/verify_core_kubernetes_final_lock.py')
    coverage = read('scripts/verify_feature_test_coverage.py')
    require(
        'python scripts/verify_inventory_final_lock.py' in quality_gate,
        'quality_gate.sh must run Inventory final lock.',
        errors,
    )
    require(
        'verify_inventory_final_lock.py' in core_lock,
        'Core Kubernetes lock must own Inventory final lock.',
        errors,
    )
    for required_test in (
        'tests/contracts/kubernetes/test_inventory_final_release_contract.py',
        'tests/unit/kubernetes/inventory/test_inventory_topology_selection.py',
        'tests/kubernetes/inventory/test_inventory_route_characterization.py',
        'tests/security/kubernetes/inventory/test_inventory_security.py',
        'tests/rendering/kubernetes/inventory/test_inventory_rendering.py',
        'tests/integration/kubernetes/inventory/test_node_inventory_read_model.py',
        'tests/e2e/kubernetes/inventory/test_inventory_smoke.py',
    ):
        require(required_test in coverage, f'Inventory release evidence is not permanent: {required_test}', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Kubernetes Inventory Final Lock v1 passed: AuthZ-first HTMX blocking, committed-snapshot reads, '
        'canonical template routing, blocker-safe Snapshot visibility, Hero/table/modal/pagination composition, '
        'topology DB ownership, zero residual helpers, and L0–L7 '
        'release evidence are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
