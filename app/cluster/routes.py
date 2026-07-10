from __future__ import annotations

from time import perf_counter

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.cluster.forms import ClusterCreateForm, ClusterEditForm
from app.cluster.service import (
    build_cluster_context,
    create_cluster,
    delete_cluster,
    get_cluster_by_id,
    run_test_cluster,
    update_cluster,
)
from app.inventory.service import sync_inventory
from app.models import Cluster
from app.notifications.service import (
    create_notification,
    get_navigation_notification_context,
)
from app.rbac.decorators import permission_required

cluster_bp = Blueprint(
    'cluster',
    __name__,
    url_prefix='/clusters',
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


@cluster_bp.route('/')
@permission_required('clusters.view')
def list_clusters() -> ResponseReturnValue:
    return render_template(
        'cluster/index.html',
        **_build_cluster_context_from_request(),
    )


@cluster_bp.route('/table')
@permission_required('clusters.view')
def cluster_table() -> ResponseReturnValue:
    return render_template(
        'cluster/partials/_table.html',
        **_build_cluster_context_from_request(),
    )


@cluster_bp.route(
    '/sync-all',
    methods=[
        'POST',
    ],
)
@permission_required('clusters.sync')
def sync_all_clusters() -> ResponseReturnValue:
    started_at = perf_counter()
    clusters = Cluster.query.order_by(
        Cluster.name.asc(),
    ).all()

    is_htmx = request.headers.get(
        'HX-Request',
    ) == 'true'

    view_url = url_for(
        'cluster.list_clusters',
    )

    if not clusters:
        status = 'warning'
        title = 'Sync skipped'
        message = 'No Kubernetes clusters are registered yet.'
        detail = 'Add a Kubernetes cluster before running global inventory sync.'
        duration_seconds = round(
            perf_counter() - started_at,
            1,
        )

        create_notification(
            user_id=current_user.id,
            event_type='kubernetes_inventory_sync',
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url=view_url,
            metadata={
                'total_count': 0,
                'synced_count': 0,
                'failed_count': 0,
                'duration_seconds': duration_seconds,
            },
        )

        if is_htmx:
            notification_context = get_navigation_notification_context(
                user_id=current_user.id,
            )

            return render_template(
                'components/navigation/_quick_sync_result.html',
                status=status,
                title=title,
                message=message,
                detail=detail,
                view_url=view_url,
                total_count=0,
                synced_count=0,
                failed_count=0,
                duration_seconds=duration_seconds,
                completed_label='Completed just now',
                notification_context=notification_context,
            )

        flash(
            message,
            'danger' if status == 'error' else status,
        )
        return redirect(
            request.referrer or view_url,
        )

    synced_count = 0
    failed_clusters: list[str] = []

    for cluster in clusters:
        try:
            sync_inventory(
                cluster,
            )
            synced_count += 1
        except Exception:
            failed_clusters.append(
                cluster.name,
            )

    total_count = len(clusters)
    failed_count = len(
        failed_clusters,
    )
    duration_seconds = round(
        perf_counter() - started_at,
        1,
    )

    if failed_count == total_count:
        status = 'error'
        title = 'Kubernetes sync failed'
        message = f'All {total_count} registered clusters failed to synchronize.'
        failed_preview = ', '.join(
            failed_clusters[:3],
        )
        if failed_count > 3:
            failed_preview = f'{failed_preview}, +{failed_count - 3} more'
        detail = f'Failed clusters: {failed_preview}. Review cluster access, TLS settings, and Kubernetes API compatibility.'
    elif failed_count:
        status = 'warning'
        title = 'Sync completed with warnings'
        message = f'{synced_count} clusters synced and {failed_count} failed.'
        failed_preview = ', '.join(
            failed_clusters[:3],
        )
        if failed_count > 3:
            failed_preview = f'{failed_preview}, +{failed_count - 3} more'
        detail = f'Failed clusters: {failed_preview}. Successful cluster inventory has still been refreshed.'
    else:
        status = 'success'
        title = 'Kubernetes sync completed'
        message = f'All {synced_count} registered clusters synchronized successfully.'
        detail = 'Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, and storage inventory are now refreshed.'

    create_notification(
        user_id=current_user.id,
        event_type='kubernetes_inventory_sync',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=view_url,
        metadata={
            'total_count': total_count,
            'synced_count': synced_count,
            'failed_count': failed_count,
            'duration_seconds': duration_seconds,
            'failed_clusters': failed_clusters,
        },
    )

    if is_htmx:
        notification_context = get_navigation_notification_context(
            user_id=current_user.id,
        )

        return render_template(
            'components/navigation/_quick_sync_result.html',
            status=status,
            title=title,
            message=message,
            detail=detail,
            view_url=view_url,
            total_count=total_count,
            synced_count=synced_count,
            failed_count=failed_count,
            duration_seconds=duration_seconds,
            completed_label='Completed just now',
            notification_context=notification_context,
        )

    flash(
        f'{title}. {message}',
        'danger' if status == 'error' else status,
    )
    return redirect(
        request.referrer or view_url,
    )


def _get_cluster_or_404(cluster_id: str) -> Cluster:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    return cluster


@cluster_bp.route(
    '/add',
    methods=[
        'GET',
        'POST',
    ],
)
@permission_required('clusters.manage')
def add_cluster() -> ResponseReturnValue:
    form = ClusterCreateForm()

    if form.validate_on_submit():
        kube_file = form.kubeconfig.data

        if kube_file is None:
            flash(
                'Kubeconfig file is required',
                'danger',
            )

            return render_template(
                'cluster/add.html',
                form=form,
            )

        try:
            kube_content = kube_file.read().decode(
                'utf-8',
            )

            assert form.name.data is not None
            assert form.environment.data is not None
            assert form.kubeconfig.data is not None

            create_cluster(
                name=form.name.data,
                environment=form.environment.data,
                description=form.description.data,
                kubeconfig=kube_content,
                kube_verify_ssl=bool(
                    form.kube_verify_ssl.data,
                ),
                kube_allow_weak_tls=bool(
                    form.kube_allow_weak_tls.data,
                ),
            )

            flash(
                'Cluster added successfully',
                'success',
            )

            return redirect(
                url_for(
                    'cluster.list_clusters',
                )
            )

        except ValueError as exc:
            flash(
                str(
                    exc,
                ),
                'danger',
            )

    return render_template(
        'cluster/add.html',
        form=form,
    )


@cluster_bp.route(
    '/<string:cluster_id>/test',
    methods=[
        'POST',
    ],
)
@permission_required('clusters.sync')
def test_cluster(cluster_id: str) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )
    result = run_test_cluster(
        cluster,
    )

    if result['success']:
        flash(
            'Cluster connected successfully',
            'success',
        )
    else:
        flash(
            result['error'],
            'danger',
        )

    return render_template(
        'cluster/partials/_table.html',
        **_build_cluster_context_from_request(),
    )


@cluster_bp.route(
    '/<string:cluster_id>/edit',
    methods=[
        'GET',
        'POST',
    ],
)
@permission_required('clusters.manage')
def edit_cluster(cluster_id: str) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )

    form = ClusterEditForm(
        obj=cluster,
    )

    if form.validate_on_submit():
        name = form.name.data
        environment = form.environment.data

        assert name is not None
        assert environment is not None

        try:
            update_cluster(
                cluster=cluster,
                name=name,
                environment=environment,
                description=form.description.data,
                kube_verify_ssl=bool(
                    form.kube_verify_ssl.data,
                ),
                kube_allow_weak_tls=bool(
                    form.kube_allow_weak_tls.data,
                ),
            )

            flash(
                'Cluster updated successfully',
                'success',
            )

            return redirect(
                url_for(
                    'cluster.list_clusters',
                )
            )

        except ValueError as exc:
            flash(
                str(
                    exc,
                ),
                'danger',
            )

    return render_template(
        'cluster/edit.html',
        form=form,
        cluster=cluster,
    )


@cluster_bp.route(
    '/<string:cluster_id>/delete',
    methods=[
        'POST',
    ],
)
@permission_required('clusters.manage')
def delete_cluster_route(cluster_id: str) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )

    delete_cluster(
        cluster,
    )

    flash(
        'Cluster deleted successfully',
        'success',
    )

    return redirect(
        url_for(
            'cluster.list_clusters',
        )
    )
