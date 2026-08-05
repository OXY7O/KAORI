import logging
from typing import Any

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.cluster.onboarding import has_registered_clusters
from app.cluster.service import build_cluster_context
from app.cluster.sync_jobs import enqueue_cluster_inventory_sync
from app.common.pagination import paginate_sequence
from app.inventory.overview import (
    get_cluster_by_id,
    get_inventory_clusters,
    get_inventory_freshness_context,
    get_inventory_overview,
)
from app.inventory.resources.configuration import (
    get_configuration_detail,
    get_configuration_filter_namespaces,
    get_configuration_inventory_view,
)
from app.inventory.resources.ingresses import (
    get_ingress_detail,
    get_ingress_filter_classes,
    get_ingress_filter_namespaces,
    get_ingress_inventory,
)
from app.inventory.resources.namespaces import (
    get_namespace_detail,
    get_namespace_filter_statuses,
    get_namespace_inventory,
)
from app.inventory.resources.nodes import (
    get_node_detail,
    get_node_filter_roles,
    get_node_filter_statuses,
    get_node_inventory,
)
from app.inventory.resources.pods import (
    get_pod_detail,
    get_pod_filter_namespaces,
    get_pod_filter_nodes,
    get_pod_filter_owner_types,
    get_pod_filter_statuses,
    get_pod_inventory,
)
from app.inventory.resources.services import (
    get_service_detail,
    get_service_filter_namespaces,
    get_service_filter_types,
    get_service_inventory,
)
from app.inventory.resources.storage import (
    get_storage_detail,
    get_storage_filter_namespaces,
    get_storage_filter_statuses,
    get_storage_filter_types,
    get_storage_inventory_view,
)
from app.inventory.resources.workloads import (
    get_workload_detail,
    get_workload_filter_namespaces,
    get_workload_filter_statuses,
    get_workload_filter_types,
    get_workload_inventory,
)
from app.inventory.topology.service import build_topology_graph, build_topology_page_context
from app.notifications.service import (
    get_navigation_notification_context,
    queue_quick_action_feedback,
    record_operational_activity,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

_INVENTORY_PARTIAL_TEMPLATES = {
    resource: {
        'index': f'inventory/{resource}/index.html',
        'scope': f'inventory/{resource}/partials/_inventory_scope.html',
        'card': f'inventory/{resource}/partials/_table_card.html',
        'content': f'inventory/{resource}/partials/_table_content.html',
    }
    for resource in (
        'nodes',
        'namespaces',
        'configuration',
        'workloads',
        'pods',
        'services',
        'ingresses',
        'storage',
    )
}
_INVENTORY_PARTIAL_TEMPLATES['nodes']['workspace'] = 'inventory/nodes/partials/_page_workspace.html'
_INVENTORY_PARTIAL_TEMPLATES['namespaces']['workspace'] = 'inventory/namespaces/partials/_page_workspace.html'

inventory_bp = Blueprint(
    'inventory',
    __name__,
    url_prefix='/inventory',
)


@inventory_bp.context_processor
def inject_inventory_freshness_context() -> dict[str, Any]:
    """Expose one consistent snapshot timestamp across every Inventory page."""
    cluster_id = request.args.get('cluster_id', '', type=str)
    return {'inventory_freshness': get_inventory_freshness_context(cluster_id=cluster_id)}


@inventory_bp.before_request
def block_clusterless_inventory_partials():
    """Keep direct HTMX inventory requests aligned with the full-page blocker."""
    if request.method != 'GET' or request.headers.get('HX-Request') != 'true':
        return None

    if has_registered_clusters() is False:
        return render_template(
            'components/cluster/_onboarding_banner.html',
        )

    return None


@inventory_bp.post('/<string:cluster_id>/sync')
@permission_required('clusters.sync')
def sync(cluster_id: str):
    cluster = get_cluster_by_id(cluster_id)
    if cluster is None:
        abort(404)

    try:
        job, created = enqueue_cluster_inventory_sync(
            cluster=cluster,
            requested_by_user_id=int(current_user.id),
        )
    except Exception:
        logger.exception('Could not enqueue canonical inventory synchronization for cluster %s.', cluster.id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='kubernetes_inventory_sync',
            status='error',
            title='Cluster inventory sync could not start',
            message=f'{cluster.name} inventory synchronization could not be queued.',
            detail='Verify PostgreSQL, Redis, and the Celery inventory worker before retrying.',
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster.id),
            action_label='Review Kubernetes connection',
            action_icon='server',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'scope': 'single_cluster',
            },
        )
        if request.headers.get('HX-Request') == 'true':
            return render_template(
                'components/navigation/_quick_sync_result.html',
                **feedback,
                toast_oob=True,
                notification_context=get_navigation_notification_context(user_id=current_user.id),
            ), 503
        queue_quick_action_feedback(feedback)
        return redirect(request.referrer or url_for('integrations.kubernetes'))

    metadata = {
        'cluster_id': cluster.id,
        'cluster_name': cluster.name,
        'requested_by_user_id': current_user.id,
        'created_at': job.queued_at.isoformat() if job.queued_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'status': 'info',
        'title': 'Cluster inventory sync in progress',
        'message': (
            f'Synchronizing Kubernetes inventory for {cluster.name}.'
            if created
            else f'Using the active Kubernetes inventory job for {cluster.name}.'
        ),
        'task_id': str(job.celery_task_id),
        'job_execution_id': job.id,
        'celery_state': 'PENDING',
        'state_label': 'pending',
        'elapsed_seconds': 0,
    }
    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'components/navigation/_individual_sync_status.html',
            sync=metadata,
        ), 202
    return redirect(request.referrer or url_for('integrations.kubernetes'))


def _inventory_template(resource: str) -> str:
    templates = _INVENTORY_PARTIAL_TEMPLATES[resource]
    if request.headers.get('HX-Request') != 'true':
        return templates['index']

    partial_mode = request.args.get('partial_mode', '', type=str)
    hx_target = request.headers.get('HX-Target', '')

    if partial_mode == 'table_content' or hx_target == f'{resource}-table-content':
        return templates['content']

    if partial_mode == 'inventory_scope' or hx_target == f'{resource}-inventory-scope':
        return templates['scope']

    if partial_mode == 'page_workspace' or hx_target == f'{resource}-page-workspace':
        return templates.get('workspace', templates['scope'])

    return templates['card']


def _inventory_cluster_scope(cluster_id: str) -> tuple[list[Any], str]:
    clusters = get_inventory_clusters()
    valid_cluster_ids = {str(cluster.id) for cluster in clusters}
    if cluster_id and cluster_id not in valid_cluster_ids:
        return clusters, ''
    return clusters, cluster_id


def _inventory_scope_label(clusters: list[Any], cluster_id: str) -> str:
    return next((item.name for item in clusters if str(item.id) == str(cluster_id)), 'All Clusters')


@inventory_bp.route('/')
@permission_required('inventory.view')
def overview():
    cluster_page = request.args.get(
        'cluster_page',
        1,
        type=int,
    )

    cluster_per_page = request.args.get(
        'cluster_per_page',
        5,
        type=int,
    )

    overview = get_inventory_overview()

    paginated_clusters, resources_pagination = paginate_sequence(
        overview.get(
            'clusters',
            [],
        ),
        page=cluster_page,
        per_page=cluster_per_page,
    )

    overview['clusters'] = paginated_clusters
    overview['resources_pagination'] = resources_pagination

    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'inventory/overview/partials/_resources_by_cluster_content.html',
            overview=overview,
        )

    return render_template(
        'inventory/overview/index.html',
        overview=overview,
    )


@inventory_bp.get('/topology')
@permission_required('inventory.view')
def topology():
    context = build_topology_page_context(
        cluster_id=request.args.get('cluster_id', '', type=str),
        namespace=request.args.get('namespace', '', type=str),
        scope=request.args.get('scope', 'all', type=str),
        depth=request.args.get('depth', '1', type=str),
    )

    return render_template(
        'inventory/topology/index.html',
        **context,
    )


@inventory_bp.get('/topology/data')
@permission_required('inventory.view')
def topology_data():
    graph = build_topology_graph(
        cluster_id=request.args.get('cluster_id', '', type=str),
        namespace=request.args.get('namespace', '', type=str),
        scope=request.args.get('scope', 'all', type=str),
        depth=request.args.get('depth', '1', type=str),
    )

    return jsonify(graph)


@inventory_bp.route('/nodes')
@permission_required('inventory.view')
def nodes():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    role = request.args.get('role', '', type=str)
    status = request.args.get('status', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    node_roles = get_node_filter_roles(cluster_id=cluster_id)
    node_statuses = get_node_filter_statuses(cluster_id=cluster_id)
    valid_roles = {option['value'] for option in node_roles}
    valid_statuses = {option['value'] for option in node_statuses}
    if role and role not in valid_roles:
        role = ''
    if status and status not in valid_statuses:
        status = ''

    inventory = get_node_inventory(
        cluster_id=cluster_id,
        role=role,
        status=status,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['node_roles'] = node_roles
    inventory['node_statuses'] = node_statuses
    inventory['scope_label'] = _inventory_scope_label(clusters, cluster_id)

    return render_template(
        _inventory_template('nodes'),
        inventory=inventory,
        clusters=clusters,
        cluster_id=cluster_id,
        role=role,
        selected_cluster_id=cluster_id,
        selected_role=role,
        selected_status=status,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/nodes/<int:node_id>/details')
@permission_required('inventory.view')
def node_details(node_id: int):
    node = get_node_detail(node_id)
    if node is None:
        abort(404)
    return render_template('inventory/nodes/partials/_node_detail_content.html', node=node)


@inventory_bp.route('/namespaces')
@permission_required('inventory.view')
def namespaces():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    status = request.args.get('status', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    namespace_statuses = get_namespace_filter_statuses(cluster_id=cluster_id)
    if status and status not in namespace_statuses:
        status = ''

    inventory = get_namespace_inventory(
        cluster_id=cluster_id,
        status=status,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['namespace_statuses'] = namespace_statuses
    inventory['scope_label'] = _inventory_scope_label(clusters, cluster_id)

    return render_template(
        _inventory_template('namespaces'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_status=status,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/namespaces/<int:namespace_id>/details')
@permission_required('inventory.view')
def namespace_details(namespace_id: int):
    namespace = get_namespace_detail(namespace_id)
    if namespace is None:
        abort(404)
    return render_template(
        'inventory/namespaces/partials/_namespace_detail_content.html',
        namespace=namespace,
    )


@inventory_bp.route('/configuration')
@permission_required('inventory.view')
def configuration():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    namespace = request.args.get('namespace', '', type=str)
    object_type = request.args.get('type', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    namespaces = get_configuration_filter_namespaces(cluster_id=cluster_id)
    if namespace and namespace not in namespaces:
        namespace = ''

    object_types = ['ConfigMap', 'Secret']
    if object_type and object_type not in object_types:
        object_type = ''

    inventory = get_configuration_inventory_view(
        cluster_id=cluster_id,
        namespace=namespace,
        object_type=object_type,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['namespaces'] = namespaces
    inventory['types'] = object_types

    return render_template(
        _inventory_template('configuration'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=object_type,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/configuration/<int:configuration_id>/details')
@permission_required('inventory.view')
def configuration_details(configuration_id: int):
    item = get_configuration_detail(configuration_id)
    if item is None:
        abort(404)
    return render_template(
        'inventory/configuration/partials/_configuration_detail_content.html',
        item=item,
    )


@inventory_bp.route('/workloads')
@permission_required('inventory.view')
def workloads():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    namespace = request.args.get('namespace', '', type=str)
    workload_type = request.args.get('type', '', type=str)
    status = request.args.get('status', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    namespaces = get_workload_filter_namespaces(cluster_id=cluster_id)
    if namespace and namespace not in namespaces:
        namespace = ''

    workload_types = get_workload_filter_types(
        cluster_id=cluster_id,
        namespace=namespace,
    )
    if workload_type and workload_type not in workload_types:
        workload_type = ''

    workload_statuses = get_workload_filter_statuses(
        cluster_id=cluster_id,
        namespace=namespace,
        workload_type=workload_type,
    )
    if status and status not in workload_statuses:
        status = ''

    inventory = get_workload_inventory(
        cluster_id=cluster_id,
        namespace=namespace,
        workload_type=workload_type,
        status=status,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['namespaces'] = namespaces
    inventory['workload_types'] = workload_types
    inventory['workload_statuses'] = workload_statuses
    inventory['scope_label'] = _inventory_scope_label(clusters, cluster_id)

    return render_template(
        _inventory_template('workloads'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=workload_type,
        selected_status=status,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/workloads/<int:workload_id>/details')
@permission_required('inventory.view')
def workload_details(workload_id: int):
    workload = get_workload_detail(workload_id)
    if workload is None:
        abort(404)
    return render_template(
        'inventory/workloads/partials/_workload_detail_content.html',
        workload=workload,
    )


@inventory_bp.route('/pods')
@permission_required('inventory.view')
def pods():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    namespace = request.args.get('namespace', '', type=str)
    status = request.args.get('status', '', type=str)
    owner_type = request.args.get('owner_type', '', type=str)
    node = request.args.get('node', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    namespaces = get_pod_filter_namespaces(cluster_id=cluster_id)
    if namespace and namespace not in namespaces:
        namespace = ''

    owner_types = get_pod_filter_owner_types(cluster_id=cluster_id, namespace=namespace)
    if owner_type and owner_type not in owner_types:
        owner_type = ''

    pod_statuses = get_pod_filter_statuses(
        cluster_id=cluster_id,
        namespace=namespace,
        owner_type=owner_type,
    )
    nodes = get_pod_filter_nodes(
        cluster_id=cluster_id,
        namespace=namespace,
        owner_type=owner_type,
    )
    if status and status not in pod_statuses:
        status = ''
    if node and node not in nodes:
        node = ''

    inventory = get_pod_inventory(
        cluster_id=cluster_id,
        namespace=namespace,
        status=status,
        owner_type=owner_type,
        node=node,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['namespaces'] = namespaces
    inventory['pod_statuses'] = pod_statuses
    inventory['owner_types'] = owner_types
    inventory['nodes'] = nodes
    inventory['scope_label'] = next(
        (cluster.name for cluster in clusters if str(cluster.id) == str(cluster_id)),
        'All Clusters',
    )

    return render_template(
        _inventory_template('pods'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_status=status,
        selected_owner_type=owner_type,
        selected_node=node,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/pods/<int:pod_id>/details')
@permission_required('inventory.view')
def pod_details(pod_id: int):
    pod = get_pod_detail(
        pod_id,
    )

    if pod is None:
        abort(404)

    return render_template(
        'inventory/pods/partials/_pod_detail_content.html',
        pod=pod,
    )


@inventory_bp.route('/services')
@permission_required('inventory.view')
def services():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    namespace = request.args.get('namespace', '', type=str)
    service_type = request.args.get('type', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    namespaces = get_service_filter_namespaces(cluster_id=cluster_id)
    if namespace and namespace not in namespaces:
        namespace = ''

    service_types = get_service_filter_types(cluster_id=cluster_id, namespace=namespace)
    if service_type and service_type not in service_types:
        service_type = ''

    inventory = get_service_inventory(
        cluster_id=cluster_id,
        namespace=namespace,
        service_type=service_type,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['namespaces'] = namespaces
    inventory['service_filter_types'] = service_types
    inventory['scope_label'] = next(
        (cluster.name for cluster in clusters if str(cluster.id) == str(cluster_id)),
        'All Clusters',
    )

    return render_template(
        _inventory_template('services'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=service_type,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/services/<int:service_id>/details')
@permission_required('inventory.view')
def service_details(service_id: int):
    service = get_service_detail(service_id)
    if service is None:
        abort(404)
    return render_template(
        'inventory/services/partials/_service_detail_content.html',
        service=service,
    )


@inventory_bp.route('/ingresses')
@permission_required('inventory.view')
def ingresses():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    namespace = request.args.get('namespace', '', type=str)
    ingress_class = request.args.get('class', '', type=str)
    tls_status = request.args.get('tls', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    if tls_status not in {'', 'enabled', 'disabled'}:
        tls_status = ''

    namespaces = get_ingress_filter_namespaces(cluster_id=cluster_id)
    if namespace and namespace not in namespaces:
        namespace = ''

    ingress_classes = get_ingress_filter_classes(cluster_id=cluster_id, namespace=namespace)
    if ingress_class and ingress_class not in ingress_classes:
        ingress_class = ''

    inventory = get_ingress_inventory(
        cluster_id=cluster_id,
        namespace=namespace,
        ingress_class=ingress_class,
        tls_status=tls_status,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['classes'] = ingress_classes
    inventory['namespaces'] = namespaces
    inventory['scope_label'] = next(
        (cluster.name for cluster in clusters if str(cluster.id) == str(cluster_id)),
        'All Clusters',
    )

    return render_template(
        _inventory_template('ingresses'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_class=ingress_class,
        selected_tls=tls_status,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/ingresses/<int:ingress_id>/details')
@permission_required('inventory.view')
def ingress_details(ingress_id: int):
    ingress = get_ingress_detail(ingress_id)
    if ingress is None:
        abort(404)
    return render_template(
        'inventory/ingresses/partials/_ingress_detail_content.html',
        ingress=ingress,
    )


@inventory_bp.route('/storage')
@permission_required('inventory.view')
def storage():
    clusters, cluster_id = _inventory_cluster_scope(request.args.get('cluster_id', '', type=str))
    namespace = request.args.get('namespace', '', type=str)
    storage_type = request.args.get('type', '', type=str)
    status = request.args.get('status', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)

    namespaces = get_storage_filter_namespaces(cluster_id=cluster_id)
    if namespace and namespace not in namespaces:
        namespace = ''

    storage_types = get_storage_filter_types(cluster_id=cluster_id, namespace=namespace)
    if storage_type and storage_type not in storage_types:
        storage_type = ''

    storage_statuses = get_storage_filter_statuses(
        cluster_id=cluster_id,
        namespace=namespace,
        storage_type=storage_type,
    )
    if status and status not in storage_statuses:
        status = ''

    inventory = get_storage_inventory_view(
        cluster_id=cluster_id,
        namespace=namespace,
        storage_type=storage_type,
        status=status,
        search=search,
        page=page,
        per_page=per_page,
    )
    inventory['namespaces'] = namespaces
    inventory['storage_filter_types'] = storage_types
    inventory['storage_filter_statuses'] = storage_statuses

    return render_template(
        _inventory_template('storage'),
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=storage_type,
        selected_status=status,
        search=search,
        pagination=inventory['pagination'],
    )


@inventory_bp.get('/storage/<int:storage_id>/details')
@permission_required('inventory.view')
def storage_details(storage_id: int):
    storage_item = get_storage_detail(storage_id)
    if storage_item is None:
        abort(404)
    return render_template(
        'inventory/storage/partials/_storage_detail_content.html',
        item=storage_item,
    )


def _build_cluster_context_from_request() -> dict:
    return build_cluster_context(
        page=request.args.get('page', '1'),
        per_page=request.args.get('per_page', '5'),
        search=request.args.get('search', ''),
        environment=request.args.get('environment', 'all'),
    )
