import logging

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.cluster.onboarding import has_registered_clusters
from app.cluster.service import build_cluster_context
from app.inventory.topology import build_topology_graph, build_topology_page_context
from app.inventory.service import (
    get_cluster_by_id,
    get_configuration_detail,
    get_configuration_inventory_view,
    get_ingress_detail,
    get_ingress_filter_classes,
    get_ingress_inventory,
    get_inventory_clusters,
    get_inventory_overview,
    get_namespace_detail,
    get_namespace_filter_statuses,
    get_namespace_inventory,
    get_node_detail,
    get_node_filter_roles,
    get_node_filter_statuses,
    get_node_inventory,
    get_pod_detail,
    get_pod_filter_namespaces,
    get_pod_filter_nodes,
    get_pod_filter_owner_types,
    get_pod_filter_statuses,
    get_pod_inventory,
    get_service_detail,
    get_service_filter_types,
    get_service_inventory,
    get_storage_detail,
    get_storage_filter_statuses,
    get_storage_filter_types,
    get_storage_inventory_view,
    get_workload_detail,
    get_workload_filter_namespaces,
    get_workload_filter_statuses,
    get_workload_filter_types,
    get_workload_inventory,
    sync_inventory,
)
from app.notifications.service import (
    get_navigation_notification_context,
    queue_quick_action_feedback,
    record_operational_activity,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

inventory_bp = Blueprint(
    'inventory',
    __name__,
    url_prefix='/inventory',
)


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
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(404)

    try:
        sync_inventory(cluster)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='kubernetes_inventory_sync',
            status='success',
            title='Cluster inventory synchronized',
            message=f'{cluster.name} inventory was refreshed successfully.',
            detail='Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, and storage snapshots are now up to date.',
            action_url=url_for('cluster.list_clusters'),
            action_label='View clusters',
            action_icon='server',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'scope': 'single_cluster',
            },
        )
    except Exception as exc:
        logger.exception(
            'Inventory synchronization failed for cluster %s.',
            cluster.id,
        )
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='kubernetes_inventory_sync',
            status='error',
            title='Cluster inventory sync failed',
            message=f'{cluster.name} inventory could not be refreshed.',
            detail=(
                f'{type(exc).__name__}: review Kubernetes API compatibility, cluster credentials, TLS settings, '
                'and application logs before retrying.'
            ),
            action_url=url_for('cluster.edit_cluster', cluster_id=cluster.id),
            action_label='Review cluster settings',
            action_icon='settings-2',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'scope': 'single_cluster',
                'reason': type(exc).__name__,
            },
        )

    if request.headers.get('HX-Request') == 'true':
        table_html = render_template(
            'cluster/partials/_table.html',
            **_build_cluster_context_from_request(),
        )
        toast_html = render_template(
            'components/navigation/_quick_sync_result.html',
            **feedback,
            toast_oob=True,
            notification_context=get_navigation_notification_context(
                user_id=current_user.id,
            ),
        )
        return f'{table_html}{toast_html}'

    queue_quick_action_feedback(feedback)
    return redirect(request.referrer or url_for('cluster.list_clusters'))


def _paginate_resource_clusters(rows, page: int, per_page: int) -> tuple[list[dict], dict]:
    allowed_per_page = [5, 10, 25, 50]

    if per_page not in allowed_per_page:
        per_page = 5

    if page < 1:
        page = 1

    total_items = len(rows)
    total_pages = max((total_items + per_page - 1) // per_page, 1)

    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    pagination = {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start_index + 1 if total_items > 0 else 0,
        'end_item': min(end_index, total_items),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed_per_page,
    }

    return rows[start_index:end_index], pagination


def _build_pagination(
    total_items: int,
    page: int,
    per_page: int,
    allowed_per_page: list[int],
) -> tuple[int, int, dict]:
    if per_page not in allowed_per_page:
        per_page = allowed_per_page[0]

    if page < 1:
        page = 1

    total_pages = max(
        (total_items + per_page - 1) // per_page,
        1,
    )

    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    pagination = {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start_index + 1 if total_items > 0 else 0,
        'end_item': min(
            end_index,
            total_items,
        ),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed_per_page,
    }

    return start_index, end_index, pagination


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

    paginated_clusters, resources_pagination = _paginate_resource_clusters(
        overview.get(
            'clusters',
            [],
        ),
        cluster_page,
        cluster_per_page,
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
    cluster_id = request.args.get(
        'cluster_id',
        '',
        type=str,
    )

    role = request.args.get(
        'role',
        '',
        type=str,
    )

    status = request.args.get(
        'status',
        '',
        type=str,
    )

    search = request.args.get(
        'search',
        '',
        type=str,
    ).strip()

    page = request.args.get(
        'page',
        1,
        type=int,
    )

    per_page = request.args.get(
        'per_page',
        5,
        type=int,
    )

    allowed_per_page = [
        5,
        10,
        25,
        50,
    ]

    data = get_node_inventory(
        cluster_id=cluster_id,
        role=role,
        status=status,
        search=search,
    )

    data['node_roles'] = get_node_filter_roles(
        cluster_id=cluster_id,
    )

    data['node_statuses'] = get_node_filter_statuses(
        cluster_id=cluster_id,
    )

    if role and role not in data['node_roles']:
        role = ''
        data = get_node_inventory(
            cluster_id=cluster_id,
            role=role,
            status=status,
            search=search,
        )
        data['node_roles'] = get_node_filter_roles(
            cluster_id=cluster_id,
        )
        data['node_statuses'] = get_node_filter_statuses(
            cluster_id=cluster_id,
        )

    if status and status not in data['node_statuses']:
        status = ''
        data = get_node_inventory(
            cluster_id=cluster_id,
            role=role,
            status=status,
            search=search,
        )
        data['node_roles'] = get_node_filter_roles(
            cluster_id=cluster_id,
        )
        data['node_statuses'] = get_node_filter_statuses(
            cluster_id=cluster_id,
        )

    all_nodes = data.get(
        'nodes',
        [],
    )

    start_index, end_index, pagination = _build_pagination(
        total_items=len(
            all_nodes,
        ),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )

    data['nodes'] = all_nodes[start_index:end_index]

    clusters = get_inventory_clusters()

    template_name = (
        'inventory/nodes/partials/_table_content.html'
        if request.headers.get('HX-Request') == 'true'
        else 'inventory/nodes/index.html'
    )

    return render_template(
        template_name,
        inventory=data,
        clusters=clusters,
        cluster_id=cluster_id,
        role=role,
        selected_cluster_id=cluster_id,
        selected_role=role,
        selected_status=status,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get(
        'cluster_id',
        '',
        type=str,
    )

    status = request.args.get(
        'status',
        '',
        type=str,
    )

    search = request.args.get(
        'search',
        '',
        type=str,
    ).strip()

    page = request.args.get(
        'page',
        1,
        type=int,
    )

    per_page = request.args.get(
        'per_page',
        5,
        type=int,
    )

    allowed_per_page = [
        5,
        10,
        25,
        50,
    ]

    data = get_namespace_inventory(
        cluster_id=cluster_id,
        status=status,
        search=search,
    )

    data['namespace_statuses'] = get_namespace_filter_statuses(
        cluster_id=cluster_id,
    )

    if status and status not in data['namespace_statuses']:
        status = ''
        data = get_namespace_inventory(
            cluster_id=cluster_id,
            status=status,
            search=search,
        )
        data['namespace_statuses'] = get_namespace_filter_statuses(
            cluster_id=cluster_id,
        )

    all_namespaces = data.get(
        'namespaces',
        [],
    )

    start_index, end_index, pagination = _build_pagination(
        total_items=len(
            all_namespaces,
        ),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )

    data['namespaces'] = all_namespaces[start_index:end_index]

    clusters = get_inventory_clusters()

    template_name = (
        'inventory/namespaces/partials/_table_content.html'
        if request.headers.get('HX-Request') == 'true'
        else 'inventory/namespaces/index.html'
    )

    return render_template(
        template_name,
        inventory=data,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_status=status,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get('cluster_id', '', type=str)
    namespace = request.args.get('namespace', '', type=str)
    object_type = request.args.get('type', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    allowed_per_page = [5, 10, 25, 50]

    inventory = get_configuration_inventory_view(
        cluster_id=cluster_id,
        namespace=namespace,
        object_type=object_type,
        search=search,
    )

    if namespace and namespace not in inventory['namespaces']:
        namespace = ''
        inventory = get_configuration_inventory_view(
            cluster_id=cluster_id,
            namespace=namespace,
            object_type=object_type,
            search=search,
        )

    if object_type and object_type not in inventory['types']:
        object_type = ''
        inventory = get_configuration_inventory_view(
            cluster_id=cluster_id,
            namespace=namespace,
            object_type=object_type,
            search=search,
        )

    all_items = inventory.get('items', [])
    start_index, end_index, pagination = _build_pagination(
        total_items=len(all_items),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )
    inventory['items'] = all_items[start_index:end_index]

    clusters = get_inventory_clusters()

    if request.headers.get('HX-Request') == 'true':
        partial_mode = request.args.get('partial_mode', '', type=str)
        template_name = (
            'inventory/configuration/partials/_table_content.html'
            if partial_mode == 'table_content'
            else 'inventory/configuration/partials/_table_card.html'
        )
    else:
        template_name = 'inventory/configuration/index.html'

    return render_template(
        template_name,
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=object_type,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get(
        'cluster_id',
        '',
        type=str,
    )

    namespace = request.args.get(
        'namespace',
        '',
        type=str,
    )

    workload_type = request.args.get(
        'type',
        '',
        type=str,
    )

    status = request.args.get(
        'status',
        '',
        type=str,
    )

    search = request.args.get(
        'search',
        '',
        type=str,
    ).strip()

    page = request.args.get(
        'page',
        1,
        type=int,
    )

    per_page = request.args.get(
        'per_page',
        5,
        type=int,
    )

    allowed_per_page = [
        5,
        10,
        25,
        50,
    ]

    namespaces = get_workload_filter_namespaces(
        cluster_id=cluster_id,
    )

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
    )

    if status and status not in workload_statuses:
        status = ''

    inventory = get_workload_inventory(
        cluster_id=cluster_id,
        namespace=namespace,
        workload_type=workload_type,
        status=status,
        search=search,
    )
    inventory['namespaces'] = namespaces
    inventory['workload_types'] = workload_types
    inventory['workload_statuses'] = workload_statuses

    all_workloads = inventory.get(
        'workloads',
        [],
    )

    start_index, end_index, pagination = _build_pagination(
        total_items=len(
            all_workloads,
        ),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )

    inventory['workloads'] = all_workloads[start_index:end_index]

    clusters = get_inventory_clusters()

    if request.headers.get('HX-Request') == 'true':
        partial_mode = request.args.get(
            'partial_mode',
            '',
            type=str,
        )
        template_name = (
            'inventory/workloads/partials/_table_card.html'
            if partial_mode == 'table_card'
            else 'inventory/workloads/partials/_table_content.html'
        )
    else:
        template_name = 'inventory/workloads/index.html'

    return render_template(
        template_name,
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=workload_type,
        selected_status=status,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get(
        'cluster_id',
        '',
        type=str,
    )

    namespace = request.args.get(
        'namespace',
        '',
        type=str,
    )

    status = request.args.get(
        'status',
        '',
        type=str,
    )

    owner_type = request.args.get(
        'owner_type',
        '',
        type=str,
    )

    node = request.args.get(
        'node',
        '',
        type=str,
    )

    search = request.args.get(
        'search',
        '',
        type=str,
    ).strip()

    page = request.args.get(
        'page',
        1,
        type=int,
    )

    per_page = request.args.get(
        'per_page',
        5,
        type=int,
    )

    allowed_per_page = [
        5,
        10,
        25,
        50,
    ]

    namespaces = get_pod_filter_namespaces(
        cluster_id=cluster_id,
    )
    if namespace and namespace not in namespaces:
        namespace = ''

    pod_statuses = get_pod_filter_statuses(
        cluster_id=cluster_id,
        namespace=namespace,
    )
    owner_types = get_pod_filter_owner_types(
        cluster_id=cluster_id,
        namespace=namespace,
    )
    nodes = get_pod_filter_nodes(
        cluster_id=cluster_id,
        namespace=namespace,
    )

    if status and status not in pod_statuses:
        status = ''
    if owner_type and owner_type not in owner_types:
        owner_type = ''
    if node and node not in nodes:
        node = ''

    inventory = get_pod_inventory(
        cluster_id=cluster_id,
        namespace=namespace,
        status=status,
        owner_type=owner_type,
        node=node,
        search=search,
    )
    inventory['namespaces'] = namespaces
    inventory['pod_statuses'] = pod_statuses
    inventory['owner_types'] = owner_types
    inventory['nodes'] = nodes

    all_pods = inventory.get(
        'pods',
        [],
    )

    start_index, end_index, pagination = _build_pagination(
        total_items=len(
            all_pods,
        ),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )

    inventory['pods'] = all_pods[start_index:end_index]

    clusters = get_inventory_clusters()

    if request.headers.get('HX-Request') == 'true':
        partial_mode = request.args.get(
            'partial_mode',
            '',
            type=str,
        )

        template_name = (
            'inventory/pods/partials/_table_content.html'
            if partial_mode == 'table_content'
            else 'inventory/pods/partials/_table_card.html'
        )
    else:
        template_name = 'inventory/pods/index.html'

    return render_template(
        template_name,
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_status=status,
        selected_owner_type=owner_type,
        selected_node=node,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get('cluster_id', '', type=str)
    namespace = request.args.get('namespace', '', type=str)
    service_type = request.args.get('type', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    allowed_per_page = [5, 10, 25, 50]

    def load_inventory():
        data = get_service_inventory(
            cluster_id=cluster_id,
            namespace=namespace,
            service_type=service_type,
            search=search,
        )
        data['service_filter_types'] = get_service_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        )
        return data

    inventory = load_inventory()

    if namespace and namespace not in inventory.get('namespaces', []):
        namespace = ''
        inventory = load_inventory()

    if service_type and service_type not in inventory.get('service_filter_types', []):
        service_type = ''
        inventory = load_inventory()

    all_services = inventory.get('services', [])
    start_index, end_index, pagination = _build_pagination(
        total_items=len(all_services),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )
    inventory['services'] = all_services[start_index:end_index]
    clusters = get_inventory_clusters()

    if request.headers.get('HX-Request') == 'true':
        partial_mode = request.args.get('partial_mode', '', type=str)
        template_name = (
            'inventory/services/partials/_table_content.html'
            if partial_mode == 'table_content'
            else 'inventory/services/partials/_table_card.html'
        )
    else:
        template_name = 'inventory/services/index.html'

    return render_template(
        template_name,
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=service_type,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get('cluster_id', '', type=str)
    namespace = request.args.get('namespace', '', type=str)
    ingress_class = request.args.get('class', '', type=str)
    tls_status = request.args.get('tls', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    allowed_per_page = [5, 10, 25, 50]

    if tls_status not in {'', 'enabled', 'disabled'}:
        tls_status = ''

    def load_inventory():
        data = get_ingress_inventory(
            cluster_id=cluster_id,
            namespace=namespace,
            ingress_class=ingress_class,
            tls_status=tls_status,
            search=search,
        )
        data['classes'] = get_ingress_filter_classes(
            cluster_id=cluster_id,
            namespace=namespace,
        )
        return data

    inventory = load_inventory()

    if namespace and namespace not in inventory.get('namespaces', []):
        namespace = ''
        inventory = load_inventory()

    if ingress_class and ingress_class not in inventory.get('classes', []):
        ingress_class = ''
        inventory = load_inventory()

    all_ingresses = inventory.get('ingresses', [])
    start_index, end_index, pagination = _build_pagination(
        total_items=len(all_ingresses),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )
    inventory['ingresses'] = all_ingresses[start_index:end_index]
    clusters = get_inventory_clusters()

    if request.headers.get('HX-Request') == 'true':
        partial_mode = request.args.get('partial_mode', '', type=str)
        template_name = (
            'inventory/ingresses/partials/_table_content.html'
            if partial_mode == 'table_content'
            else 'inventory/ingresses/partials/_table_card.html'
        )
    else:
        template_name = 'inventory/ingresses/index.html'

    return render_template(
        template_name,
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_class=ingress_class,
        selected_tls=tls_status,
        search=search,
        pagination=pagination,
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
    cluster_id = request.args.get('cluster_id', '', type=str)
    namespace = request.args.get('namespace', '', type=str)
    storage_type = request.args.get('type', '', type=str)
    status = request.args.get('status', '', type=str)
    search = request.args.get('search', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    allowed_per_page = [5, 10, 25, 50]

    def load_inventory():
        data = get_storage_inventory_view(
            cluster_id=cluster_id,
            namespace=namespace,
            storage_type=storage_type,
            status=status,
            search=search,
        )
        data['storage_filter_types'] = get_storage_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        )
        data['storage_filter_statuses'] = get_storage_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
            storage_type=storage_type,
        )
        return data

    inventory = load_inventory()

    if namespace and namespace not in inventory.get('namespaces', []):
        namespace = ''
        inventory = load_inventory()

    if storage_type and storage_type not in inventory.get('storage_filter_types', []):
        storage_type = ''
        inventory = load_inventory()

    if status and status not in inventory.get('storage_filter_statuses', []):
        status = ''
        inventory = load_inventory()

    all_storage = inventory.get('storage_items', [])
    start_index, end_index, pagination = _build_pagination(
        total_items=len(all_storage),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )
    inventory['storage_items'] = all_storage[start_index:end_index]
    clusters = get_inventory_clusters()

    if request.headers.get('HX-Request') == 'true':
        partial_mode = request.args.get('partial_mode', '', type=str)
        template_name = (
            'inventory/storage/partials/_table_content.html'
            if partial_mode == 'table_content'
            else 'inventory/storage/partials/_table_card.html'
        )
    else:
        template_name = 'inventory/storage/index.html'

    return render_template(
        template_name,
        inventory=inventory,
        clusters=clusters,
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_type=storage_type,
        selected_status=status,
        search=search,
        pagination=pagination,
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
        page=request.args.get(
            'page',
            '1',
        ),
        per_page=request.args.get(
            'per_page',
            '5',
        ),
        search=request.args.get(
            'search',
            '',
        ),
        environment=request.args.get(
            'environment',
            'all',
        ),
    )
