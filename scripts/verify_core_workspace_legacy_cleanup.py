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
        'app/dashboards/kubernetes/snapshot_builder.py',
        'app/analytics/kubernetes/common/cache.py',
        'app/templates/inventory/kubernetes/components/_detail_macros.html',
        'app/templates/inventory/kubernetes/nodes/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/namespaces/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/workloads/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/pods/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/services/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/ingresses/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/configuration/partials/_inventory_scope.html',
        'app/templates/inventory/kubernetes/storage/partials/_inventory_scope.html',
        'app/kubernetes_operations/secrets/routes.py',
        'app/templates/integrations/partials/_runtime_detail_content.html',
        'app/templates/prometheus/partials/_analytics_readiness.html',
        'tests/kubernetes_operations/test_secret_delete_workflow.py',
    )
    for relative in obsolete_paths:
        require(not (ROOT / relative).exists(), f'Obsolete compatibility file still exists: {relative}', errors)

    welcome_routes = read('app/welcome/routes.py')
    require(
        "@welcome_bp.route('/')" in welcome_routes and "@welcome_bp.route('/welcome')" in welcome_routes,
        'Welcome root routes must be owned directly by welcome.index.',
        errors,
    )
    require(
        'redirect(' not in welcome_routes,
        'Welcome must not redirect through a retired dashboard compatibility route.',
        errors,
    )

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
    require(
        'filter_current_generation(query, model)' in dashboard_repository,
        'Dashboard Inventory queries must read only the committed generation.',
        errors,
    )
    require(
        'from app.models import (' in dashboard_service,
        'Dashboard service must import canonical models directly.',
        errors,
    )
    require(
        'from app.models import Report, ReportSchedule, ReportTemplate' in dashboard_reporting,
        'Reporting summary must use canonical model imports.',
        errors,
    )
    require(
        "if live_cluster is not None else 'Select a cluster for a worker snapshot'" not in dashboard_kpis,
        'Dashboard KPI copy must not retain the duplicated conditional bridge.',
        errors,
    )

    analytics_catalog = read('app/analytics/kubernetes/materialization/catalog.py')
    analytics_job_adapter = read('app/analytics/kubernetes/job_adapter.py')
    dashboard_snapshots = read('app/dashboards/kubernetes/snapshots.py')
    require(
        "builder_path='app.analytics.kubernetes.materialization.dashboard_alerts:build_dashboard_alerts_context'"
        in analytics_catalog,
        'Dashboard alert materialization must be owned by Analytics.',
        errors,
    )
    require(
        'app.dashboards' not in analytics_catalog and 'app.dashboards' not in analytics_job_adapter,
        'Analytics must not import Dashboard implementation modules.',
        errors,
    )
    dashboard_service = read('app/dashboards/kubernetes/service.py')
    require(
        'from app.analytics.kubernetes.materialization.keys import (' in dashboard_service
        and 'DASHBOARD_ALERTS_DATASET_KEY' in dashboard_service
        and 'CAPACITY_DATASET_KEY' in dashboard_service
        and 'FORECAST_DATASET_KEY' in dashboard_service
        and 'TOP_CONSUMERS_DATASET_KEY' in dashboard_service,
        'Dashboard service must consume Analytics-owned dataset keys directly.',
        errors,
    )
    require(
        'app.analytics.kubernetes.materialization.keys' not in dashboard_snapshots,
        'Dashboard snapshot reader must not re-export Analytics dataset keys.',
        errors,
    )

    runtime_recovery = read('app/integrations/runtime/recovery.py')
    inventory_job_adapter = read('app/inventory/kubernetes/job_adapter.py')
    notifications_queries = read('app/notifications/queries.py')
    shared_job_presentation = read('app/common/job_execution_presentation.py')
    shared_job_contract = read('app/common/job_execution_contract.py')
    require(
        'from app.jobs.registry import get_job_definition' in runtime_recovery,
        'Integration recovery must dispatch through the registered job boundary.',
        errors,
    )
    for forbidden in (
        'from app.cluster.sync_jobs import',
        'from app.governance.tls_certificates.sync_jobs import',
        'from app.analytics.kubernetes.job_adapter import',
    ):
        require(
            forbidden not in runtime_recovery,
            f'Integration recovery must not import domain implementation directly: {forbidden}',
            errors,
        )
    require(
        "cluster_id = str((parameters or {}).get('cluster_id') or '').strip()" in inventory_job_adapter
        and 'enqueue_cluster_inventory_sync(' in inventory_job_adapter,
        'Registered Inventory dispatch must support one-cluster recovery without a wrapper.',
        errors,
    )
    require(
        'from app.common.job_execution_presentation import present_job_execution' in notifications_queries,
        'Notification Deck must use the Common-owned job presenter.',
        errors,
    )
    require(
        'app.jobs.presentation' not in notifications_queries
        and 'app.jobs.service' not in shared_job_presentation
        and 'app.jobs.registry' not in shared_job_presentation,
        'Shared job presentation must not recreate the Notifications-Jobs dependency cycle.',
        errors,
    )
    require(
        'from app.common.job_execution_contract import job_operation_label' in shared_job_presentation
        and "'tls_certificate_sync': 'TLS Certificate Sync'" in shared_job_contract,
        'Shared job operation labels must be owned by the Common execution presentation contract.',
        errors,
    )

    overview_content = read('app/templates/inventory/kubernetes/overview/partials/_resources_by_cluster_content.html')
    require(
        'hx-target="#resources-by-cluster-content"' in overview_content,
        'Inventory Overview pagination must use its canonical cluster-content boundary.',
        errors,
    )
    require(
        'inventory-scope' not in overview_content,
        'Inventory Overview must not use a generic resource scope wrapper.',
        errors,
    )

    routes = read('app/inventory/kubernetes/routes.py')
    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes,
        'Audited Inventory pages must use one canonical workspace mapping.',
        errors,
    )
    require(
        "templates.get('workspace', templates['scope'])" not in routes,
        'Inventory workspace routing must not fall back to compatibility scope wrappers.',
        errors,
    )
    require(
        '_build_cluster_context_from_request' not in routes,
        'Unused Inventory route wrapper must remain removed.',
        errors,
    )

    for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage'):
        workspace = read(f'app/templates/inventory/kubernetes/{resource}/partials/_page_workspace.html')
        table = read(f'app/templates/inventory/kubernetes/{resource}/partials/_table_content.html')
        require(
            f'id="{resource}-page-workspace"' in workspace, f'{resource} must own one canonical page workspace.', errors
        )
        require(
            f'inventory/kubernetes/{resource}/partials/_summary_cards.html' in workspace,
            f'{resource} workspace must call summary directly.',
            errors,
        )
        require(
            f'inventory/kubernetes/{resource}/partials/_table_card.html' in workspace,
            f'{resource} workspace must call table card directly.',
            errors,
        )
        require(
            f'hx-target="#{resource}-table-content"' in table,
            f'{resource} page-size control must target canonical table content.',
            errors,
        )
        require(
            'name="partial_mode" value="table_content"' in table,
            f'{resource} page-size control must request canonical table content.',
            errors,
        )

    topology_index = read('app/templates/inventory/kubernetes/topology/index.html')
    topology_script = read('app/static/js/inventory/kubernetes/topology.js')
    require(
        "filename='js/inventory/kubernetes/topology.js'" in topology_index,
        'Topology must load its canonical module directly.',
        errors,
    )
    require("'workspace_url':" not in topology_index, 'Topology must not pass a compatibility workspace URL.', errors)
    require(
        'await import(config.renderer_url)' in topology_script,
        'Topology module must import its renderer directly.',
        errors,
    )
    require(
        'window.cytoscape' not in topology_script,
        'Topology must not bridge the renderer through a global compatibility alias.',
        errors,
    )
    topology_service = read('app/inventory/kubernetes/topology/service.py')
    topology_repository = read('app/inventory/kubernetes/topology/repository.py')
    topology_node_builder = read('app/inventory/kubernetes/topology/node_builder.py')
    topology_edge_builder = read('app/inventory/kubernetes/topology/edge_builder.py')
    require(
        'TopologyGraphBuilder' in topology_service and '_node_element' not in topology_service,
        'Topology service must orchestrate the canonical graph builder without the legacy node wrapper.',
        errors,
    )
    require(
        'filter_current_generation' in topology_repository,
        'Topology repository must own committed-generation queries.',
        errors,
    )
    require(
        'class TopologyNodeBuilder' in topology_node_builder,
        'Topology node projection must use the canonical node builder.',
        errors,
    )
    require(
        'class TopologyEdgeBuilder' in topology_edge_builder,
        'Topology relationships must use the canonical edge builder.',
        errors,
    )

    workload_backend = read('app/inventory/kubernetes/resources/workloads.py')
    export_payload = read('app/reports/export/payloads/inventory.py')
    namespace_backend = read('app/inventory/kubernetes/resources/namespaces.py')
    require(
        "'running': ('Stable', 'normal')" not in workload_backend,
        'Legacy Workload state aliases must not be accepted internally.',
        errors,
    )
    require(
        "'succeeded': ('Stable', 'normal')" not in workload_backend,
        'Legacy Workload completion aliases must not be accepted internally.',
        errors,
    )
    require(
        '_detail_row_value' not in export_payload and '_detail_integer' not in export_payload,
        'Inventory export must not read legacy nested Workload evidence.',
        errors,
    )
    require(
        'legacy_port_count' not in export_payload, 'Service export must not read legacy compact port columns.', errors
    )
    require(
        "configuration.get('reported'," not in export_payload,
        'Pod export must require explicit canonical evidence flags.',
        errors,
    )
    require(
        'committed legacy generation' not in namespace_backend,
        'Namespace evidence must not infer success from legacy generations.',
        errors,
    )

    quality_gate = read('scripts/quality_gate.sh')
    require(
        'verify_core_workspace_code_health.py' in quality_gate,
        'Reviewed core workspace code-health verification must remain in the static quality gate.',
        errors,
    )

    cleanup_script = read('scripts/cleanup_obsolete_files.sh')
    for relative in obsolete_paths:
        require(
            f"'{relative}'" in cleanup_script,
            f'Obsolete path must remain registered in cleanup script: {relative}',
            errors,
        )

    service_model = read('app/models/inventory.py')
    service_collector = read('app/inventory/kubernetes/collectors/services.py')
    service_migration = read('migrations/versions/20260805_service_inventory_v2.py')
    service_class = service_model.split('class ServiceInventory', 1)[1].split('class IngressInventory', 1)[0]
    require(
        'external_ip:' not in service_class and 'ports:' not in service_class,
        'ServiceInventory duplicate presentation columns must be removed.',
        errors,
    )
    require(
        'LEGACY_TEXT_LIMIT' not in service_collector and '_bounded_legacy_text' not in service_collector,
        'Service collector must not maintain compact legacy columns.',
        errors,
    )
    require(
        "op.drop_column('service_inventory', 'ports')" in service_migration,
        'Service canonicalization migration must drop ports.',
        errors,
    )
    require(
        "op.drop_column('service_inventory', 'external_ip')" in service_migration,
        'Service canonicalization migration must drop external_ip.',
        errors,
    )

    configuration_class = service_model.split('class ConfigurationInventory', 1)[1].split(
        'class ResourceQuotaInventory', 1
    )[0]
    configuration_collector = read('app/inventory/kubernetes/collectors/configuration.py')
    configuration_migration = read('migrations/versions/20260805_config_inventory_v2.py')
    require(
        'key_count:' not in configuration_class and 'payload_size_bytes:' not in configuration_class,
        'ConfigurationInventory derived and synthetic columns must be removed.',
        errors,
    )
    require(
        "'key_count':" not in configuration_collector and "'payload_size_bytes':" not in configuration_collector,
        'Configuration collector must persist only canonical key-name evidence.',
        errors,
    )
    require(
        "op.drop_column('configuration_inventory', 'key_count')" in configuration_migration,
        'Configuration canonicalization migration must drop key_count.',
        errors,
    )
    require(
        "op.drop_column('configuration_inventory', 'payload_size_bytes')" in configuration_migration,
        'Configuration canonicalization migration must drop payload_size_bytes.',
        errors,
    )

    ingress_class = service_model.split('class IngressInventory', 1)[1].split('class StorageInventory', 1)[0]
    ingress_collector = read('app/inventory/kubernetes/collectors/ingresses.py')
    ingress_migration = read('migrations/versions/20260805_ingress_inventory_v2.py')
    require(
        'host:' not in ingress_class and 'address:' not in ingress_class,
        'IngressInventory duplicate presentation columns must be removed.',
        errors,
    )
    require(
        "'namespace': str(namespace),\n                'ingress_name': str(name),\n                'ingress_class': ingress_class,\n                'tls_enabled': bool(tls_entries)"
        in ingress_collector,
        'Ingress collector must persist only canonical top-level fields.',
        errors,
    )
    require(
        "op.drop_column('ingress_inventory', 'host')" in ingress_migration,
        'Ingress canonicalization migration must drop host.',
        errors,
    )
    require(
        "op.drop_column('ingress_inventory', 'address')" in ingress_migration,
        'Ingress canonicalization migration must drop address.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print('PASS — KAORI Core Workspace Cleanup')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
