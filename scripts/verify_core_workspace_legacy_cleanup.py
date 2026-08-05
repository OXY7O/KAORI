from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    obsolete_paths = (
        'app/static/js/inventory/topology_bootstrap.js',
        'app/templates/inventory/components/_detail_macros.html',
        'app/templates/inventory/nodes/partials/_inventory_scope.html',
        'app/templates/inventory/namespaces/partials/_inventory_scope.html',
        'app/templates/inventory/workloads/partials/_inventory_scope.html',
        'app/templates/inventory/pods/partials/_inventory_scope.html',
        'app/templates/inventory/services/partials/_inventory_scope.html',
    )
    for relative in obsolete_paths:
        require(not (ROOT / relative).exists(), f'Obsolete compatibility file still exists: {relative}', errors)

    welcome_routes = read('app/welcome/routes.py')
    require("@welcome_bp.route('/')" in welcome_routes and "@welcome_bp.route('/welcome')" in welcome_routes,
            'Welcome root routes must be owned directly by welcome.index.', errors)
    require('redirect(' not in welcome_routes,
            'Welcome must not redirect through a retired dashboard compatibility route.', errors)

    dashboard_repository = read('app/dashboards/kubernetes/repository.py')
    dashboard_service = read('app/dashboards/kubernetes/service.py')
    dashboard_reporting = read('app/dashboards/kubernetes/sections/reporting.py')
    dashboard_kpis = read('app/dashboards/kubernetes/sections/kpis.py')
    require('load_models' not in dashboard_repository, 'Dashboard dynamic model loader must be removed.', errors)
    require(
        'import_module' not in dashboard_repository,
        'Dashboard must not probe alternate model import paths.',
        errors,
    )
    require(
        'except Exception' not in dashboard_repository,
        'Dashboard repository must not hide canonical query failures.',
        errors,
    )
    require('filter_current_generation(query, model)' in dashboard_repository,
            'Dashboard Inventory queries must read only the committed generation.', errors)
    require(
        'from app.models import (' in dashboard_service,
        'Dashboard service must import canonical models directly.',
        errors,
    )
    require('from app.models import Report, ReportSchedule, ReportTemplate' in dashboard_reporting,
            'Reporting summary must use canonical model imports.', errors)
    require("if live_cluster is not None else 'Select a cluster for a worker snapshot'" not in dashboard_kpis,
            'Dashboard KPI copy must not retain the duplicated conditional bridge.', errors)

    overview_content = read('app/templates/inventory/overview/partials/_resources_by_cluster_content.html')
    require('hx-target="#resources-by-cluster-content"' in overview_content,
            'Inventory Overview pagination must use its canonical cluster-content boundary.', errors)
    require('inventory-scope' not in overview_content,
            'Inventory Overview must not use a generic resource scope wrapper.', errors)

    routes = read('app/inventory/routes.py')
    require("for resource in ('nodes', 'namespaces', 'workloads', 'pods', 'services')" in routes,
            'Audited Inventory pages must use canonical workspace mappings.', errors)
    require("templates.get('workspace', templates['scope'])" not in routes,
            'Inventory workspace routing must not fall back to compatibility scope wrappers.', errors)
    require('_build_cluster_context_from_request' not in routes,
            'Unused Inventory route wrapper must remain removed.', errors)

    for resource in ('nodes', 'namespaces', 'workloads', 'pods', 'services'):
        workspace = read(f'app/templates/inventory/{resource}/partials/_page_workspace.html')
        table = read(f'app/templates/inventory/{resource}/partials/_table_content.html')
        require(f'id="{resource}-page-workspace"' in workspace,
                f'{resource} must own one canonical page workspace.', errors)
        require(f'inventory/{resource}/partials/_summary_cards.html' in workspace,
                f'{resource} workspace must call summary directly.', errors)
        require(f'inventory/{resource}/partials/_table_card.html' in workspace,
                f'{resource} workspace must call table card directly.', errors)
        require(f'hx-target="#{resource}-table-content"' in table,
                f'{resource} page-size control must target canonical table content.', errors)
        require('name="partial_mode" value="table_content"' in table,
                f'{resource} page-size control must request canonical table content.', errors)

    topology_index = read('app/templates/inventory/topology/index.html')
    topology_script = read('app/static/js/inventory/topology.js')
    require("filename='js/inventory/topology.js'" in topology_index,
            'Topology must load its canonical module directly.', errors)
    require("'workspace_url':" not in topology_index,
            'Topology must not pass a compatibility workspace URL.', errors)
    require('await import(config.renderer_url)' in topology_script,
            'Topology module must import its renderer directly.', errors)
    require('window.cytoscape' not in topology_script,
            'Topology must not bridge the renderer through a global compatibility alias.', errors)
    topology_service = read('app/inventory/topology/service.py')
    topology_repository = read('app/inventory/topology/repository.py')
    topology_node_builder = read('app/inventory/topology/node_builder.py')
    topology_edge_builder = read('app/inventory/topology/edge_builder.py')
    require('TopologyGraphBuilder' in topology_service and '_node_element' not in topology_service,
            'Topology service must orchestrate the canonical graph builder without the legacy node wrapper.', errors)
    require('filter_current_generation' in topology_repository,
            'Topology repository must own committed-generation queries.', errors)
    require('class TopologyNodeBuilder' in topology_node_builder,
            'Topology node projection must use the canonical node builder.', errors)
    require('class TopologyEdgeBuilder' in topology_edge_builder,
            'Topology relationships must use the canonical edge builder.', errors)

    workload_backend = read('app/inventory/resources/workloads.py')
    export_payload = read('app/reports/export/payloads/inventory.py')
    namespace_backend = read('app/inventory/resources/namespaces.py')
    require("'running': ('Stable', 'normal')" not in workload_backend,
            'Legacy Workload state aliases must not be accepted internally.', errors)
    require("'succeeded': ('Stable', 'normal')" not in workload_backend,
            'Legacy Workload completion aliases must not be accepted internally.', errors)
    require('_detail_row_value' not in export_payload and '_detail_integer' not in export_payload,
            'Inventory export must not read legacy nested Workload evidence.', errors)
    require('legacy_port_count' not in export_payload,
            'Service export must not read legacy compact port columns.', errors)
    require("configuration.get('reported'," not in export_payload,
            'Pod export must require explicit canonical evidence flags.', errors)
    require('committed legacy generation' not in namespace_backend,
            'Namespace evidence must not infer success from legacy generations.', errors)

    quality_gate = read('scripts/quality_gate.sh')
    require('verify_core_workspace_code_health.py' in quality_gate,
            'Reviewed core workspace code-health verification must remain in the static quality gate.', errors)

    cleanup_script = read('scripts/cleanup_obsolete_files.sh')
    for relative in obsolete_paths:
        require(f"'{relative}'" in cleanup_script,
                f'Obsolete path must remain registered in cleanup script: {relative}', errors)

    service_model = read('app/models/inventory.py')
    service_collector = read('app/inventory/collectors/services.py')
    service_migration = read('migrations/versions/20260805_service_inventory_v2.py')
    service_class = service_model.split('class ServiceInventory', 1)[1].split('class IngressInventory', 1)[0]
    require('external_ip:' not in service_class and 'ports:' not in service_class,
            'ServiceInventory duplicate presentation columns must be removed.', errors)
    require('LEGACY_TEXT_LIMIT' not in service_collector and '_bounded_legacy_text' not in service_collector,
            'Service collector must not maintain compact legacy columns.', errors)
    require("op.drop_column('service_inventory', 'ports')" in service_migration,
            'Service canonicalization migration must drop ports.', errors)
    require("op.drop_column('service_inventory', 'external_ip')" in service_migration,
            'Service canonicalization migration must drop external_ip.', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI core workspace legacy cleanup passed: Welcome, Kubernetes Dashboard, Inventory Overview, '
        'Topology, Node, Namespace, Workload, Pod, and Service use canonical paths without internal wrappers.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
