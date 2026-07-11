from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from redis.exceptions import RedisError

from app.cluster.forms import ClusterCreateForm, ClusterEditForm
from app.cluster.onboarding import has_registered_clusters
from app.cluster.service import (
    build_cluster_context,
    create_cluster,
    delete_cluster,
    get_cluster_by_id,
    run_test_cluster,
    update_cluster,
)
from app.cluster.sync_state import (
    CLUSTER_SYNC_QUEUE,
    CLUSTER_SYNC_TASK_NAME,
    acquire_cluster_sync_lock,
    build_cluster_sync_snapshot,
    dismiss_cluster_sync_result,
    get_active_cluster_sync_task_id,
    is_cluster_sync_result_dismissed,
    release_cluster_sync_lock,
)
from app.models import Cluster
from app.notifications.service import (
    create_notification,
    get_navigation_notification_context,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

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
    if has_registered_clusters() is False:
        return render_template(
            'components/cluster/_onboarding_banner.html',
        )

    return render_template(
        'cluster/partials/_table.html',
        **_build_cluster_context_from_request(),
    )


def _render_sync_snapshot(
    snapshot: dict,
    *,
    response_status: int = 200,
) -> ResponseReturnValue:
    if snapshot['is_active']:
        return (
            render_template(
                'components/navigation/_quick_sync_status.html',
                sync=snapshot,
            ),
            response_status,
        )

    notification_context = get_navigation_notification_context(
        user_id=current_user.id,
    )

    return (
        render_template(
            'components/navigation/_quick_sync_result.html',
            task_id=snapshot.get('task_id'),
            status=snapshot.get('status') or 'info',
            title=snapshot.get('title') or 'Kubernetes sync finished',
            message=snapshot.get('message') or 'The background synchronization task has finished.',
            detail=snapshot.get('detail'),
            view_url=url_for('cluster.list_clusters'),
            total_count=snapshot.get('total_count', 0),
            synced_count=snapshot.get('synced_count', 0),
            failed_count=snapshot.get('failed_count', 0),
            duration_seconds=snapshot.get('duration_seconds'),
            completed_label='Completed just now',
            notification_context=notification_context,
            notification_saved=(snapshot.get('requested_by_user_id') == current_user.id),
        ),
        response_status,
    )


def _render_enqueue_error(
    *,
    message: str,
    detail: str,
    response_status: int,
) -> ResponseReturnValue:
    return (
        render_template(
            'components/navigation/_quick_sync_result.html',
            status='error',
            title='Kubernetes sync could not start',
            message=message,
            detail=detail,
            view_url=url_for('cluster.list_clusters'),
            total_count=None,
            synced_count=0,
            failed_count=0,
            duration_seconds=None,
            completed_label='Not started',
            notification_saved=False,
        ),
        response_status,
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
    is_htmx = request.headers.get('HX-Request') == 'true'
    view_url = url_for('cluster.list_clusters')
    total_count = Cluster.query.count()

    if total_count == 0:
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
                notification_saved=True,
            )

        flash(
            message,
            status,
        )
        return redirect(
            request.referrer or view_url,
        )

    try:
        active_task_id = get_active_cluster_sync_task_id()

        if active_task_id:
            active_snapshot = build_cluster_sync_snapshot(
                active_task_id,
            )

            if active_snapshot['is_active']:
                if is_htmx:
                    return _render_sync_snapshot(
                        active_snapshot,
                        response_status=202,
                    )

                flash(
                    'A Kubernetes inventory synchronization is already running.',
                    'info',
                )
                return redirect(
                    request.referrer or view_url,
                )

            release_cluster_sync_lock(
                active_task_id,
            )

        task_id = str(
            uuid4(),
        )
        created_at = datetime.now(
            UTC,
        ).isoformat()
        metadata = {
            'requested_by_user_id': current_user.id,
            'created_at': created_at,
            'total_count': total_count,
            'processed_count': 0,
            'synced_count': 0,
            'failed_count': 0,
            'current_cluster_name': None,
        }

        acquired = acquire_cluster_sync_lock(
            task_id=task_id,
            metadata=metadata,
        )

        if not acquired:
            active_task_id = get_active_cluster_sync_task_id()
            if active_task_id:
                snapshot = build_cluster_sync_snapshot(
                    active_task_id,
                )
                if is_htmx:
                    return _render_sync_snapshot(
                        snapshot,
                        response_status=202,
                    )

            flash(
                'A Kubernetes inventory synchronization is already running.',
                'info',
            )
            return redirect(
                request.referrer or view_url,
            )

        try:
            current_app.extensions['celery'].send_task(
                CLUSTER_SYNC_TASK_NAME,
                kwargs={
                    'requested_by_user_id': current_user.id,
                },
                task_id=task_id,
                queue=CLUSTER_SYNC_QUEUE,
            )
        except Exception:
            release_cluster_sync_lock(
                task_id,
            )
            raise

        snapshot = build_cluster_sync_snapshot(
            task_id,
        )

        if is_htmx:
            return _render_sync_snapshot(
                snapshot,
                response_status=202,
            )

        flash(
            'Kubernetes inventory synchronization started in the Celery worker.',
            'success',
        )
        return redirect(
            request.referrer or view_url,
        )
    except RedisError:
        logger.exception(
            'Redis could not create or read the cluster synchronization state.',
        )
        if is_htmx:
            return _render_enqueue_error(
                message='Redis is unavailable, so KAORI cannot persist the synchronization state.',
                detail='Verify the Redis container and CELERY_BROKER_URL before retrying.',
                response_status=503,
            )

        flash(
            'Redis is unavailable. Cluster synchronization was not started.',
            'danger',
        )
        return redirect(
            request.referrer or view_url,
        )
    except Exception:
        logger.exception(
            'Celery could not enqueue the cluster synchronization task.',
        )
        if is_htmx:
            return _render_enqueue_error(
                message='The Celery task could not be added to the inventory queue.',
                detail='Verify the Celery worker and Redis broker, then retry the operation.',
                response_status=503,
            )

        flash(
            'Celery could not start the cluster synchronization task.',
            'danger',
        )
        return redirect(
            request.referrer or view_url,
        )


@cluster_bp.route('/sync-all/status')
@permission_required('clusters.sync')
def active_sync_all_status() -> ResponseReturnValue:
    try:
        task_id = get_active_cluster_sync_task_id()
        if not task_id:
            return ''

        snapshot = build_cluster_sync_snapshot(task_id)
        if not snapshot['is_active'] and is_cluster_sync_result_dismissed(
            task_id=task_id,
            user_id=current_user.id,
        ):
            return ''

        return _render_sync_snapshot(snapshot)
    except RuntimeError as exc:
        logger.warning(
            'Cluster synchronization state is unavailable: %s',
            exc,
        )
        return ''
    except RedisError:
        logger.exception(
            'Redis could not restore the active cluster synchronization state.',
        )
        return ''


@cluster_bp.post('/sync-all/status/<string:task_id>/dismiss')
@permission_required('clusters.sync')
def dismiss_sync_all_status(task_id: str) -> ResponseReturnValue:
    is_htmx = request.headers.get('HX-Request') == 'true'

    try:
        snapshot = build_cluster_sync_snapshot(task_id)
        if snapshot['is_active']:
            return ('', 409) if is_htmx else redirect(url_for('cluster.list_clusters'))

        dismiss_cluster_sync_result(
            task_id=task_id,
            user_id=current_user.id,
        )
    except (RuntimeError, RedisError):
        logger.exception(
            'KAORI could not persist dismissal for cluster synchronization task %s.',
            task_id,
        )
        if is_htmx:
            return '', 503

        flash(
            'The synchronization result could not be dismissed because Redis is unavailable.',
            'danger',
        )

    if is_htmx:
        return ''

    return redirect(request.referrer or url_for('cluster.list_clusters'))


@cluster_bp.route('/sync-all/status/<string:task_id>')
@permission_required('clusters.sync')
def sync_all_status(task_id: str) -> ResponseReturnValue:
    try:
        snapshot = build_cluster_sync_snapshot(
            task_id,
        )
    except RuntimeError as exc:
        logger.warning(
            'Cluster synchronization task state is unavailable: %s',
            exc,
        )
        return _render_enqueue_error(
            message='KAORI could not read the synchronization progress.',
            detail='Redis state storage is not configured. Verify REDIS_URL and reload the page.',
            response_status=503,
        )
    except RedisError:
        logger.exception(
            'Redis could not read cluster synchronization task %s.',
            task_id,
        )
        return _render_enqueue_error(
            message='KAORI could not read the synchronization progress from Redis.',
            detail='The Celery task may still be running. Verify Redis connectivity and reload the page.',
            response_status=503,
        )

    return _render_sync_snapshot(
        snapshot,
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
