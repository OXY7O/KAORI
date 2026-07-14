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
from app.cluster.individual_sync_state import (
    build_individual_sync_snapshot,
    dismiss_individual_sync_result,
    get_tracked_individual_sync_task_ids,
    is_individual_sync_result_dismissed,
)
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
    queue_quick_action_feedback,
    record_operational_activity,
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


def _render_operational_toast(
    feedback: dict,
    *,
    toast_oob: bool = False,
) -> str:
    return render_template(
        'components/navigation/_quick_sync_result.html',
        **feedback,
        toast_oob=toast_oob,
        notification_context=get_navigation_notification_context(
            user_id=current_user.id,
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


@cluster_bp.get('/sync-individual/active')
@permission_required('clusters.sync')
def active_individual_sync_statuses() -> ResponseReturnValue:
    try:
        snapshots = []
        for task_id in get_tracked_individual_sync_task_ids(current_user.id):
            snapshot = build_individual_sync_snapshot(task_id)
            if not snapshot['is_active'] and is_individual_sync_result_dismissed(
                task_id=task_id,
                user_id=current_user.id,
            ):
                continue
            snapshots.append(snapshot)
        return render_template(
            'components/navigation/_individual_sync_collection.html',
            snapshots=snapshots,
        )
    except (RuntimeError, RedisError):
        logger.exception('Could not restore individual cluster synchronization states.')
        return ''


@cluster_bp.get('/sync-individual/status/<string:task_id>')
@permission_required('clusters.sync')
def individual_sync_status(task_id: str) -> ResponseReturnValue:
    snapshot = build_individual_sync_snapshot(task_id)
    if snapshot['is_active']:
        return render_template('components/navigation/_individual_sync_status.html', sync=snapshot)

    return render_template(
        'components/navigation/_quick_sync_result.html',
        task_id=task_id,
        dismiss_url=url_for('cluster.dismiss_individual_sync_status', task_id=task_id),
        status=snapshot['status'],
        title=snapshot['title'],
        message=snapshot['message'],
        detail=snapshot.get('detail'),
        view_url=url_for('cluster.list_clusters'),
        action_label='View clusters',
        action_icon='server',
        total_count=None,
        synced_count=1 if snapshot['status'] == 'success' else 0,
        failed_count=0 if snapshot['status'] == 'success' else 1,
        duration_seconds=snapshot.get('duration_seconds'),
        completed_label='Completed just now',
        notification_saved=True,
    )


@cluster_bp.post('/sync-individual/status/<string:task_id>/dismiss')
@permission_required('clusters.sync')
def dismiss_individual_sync_status(task_id: str) -> ResponseReturnValue:
    snapshot = build_individual_sync_snapshot(task_id)
    if snapshot['is_active']:
        return '', 409
    dismiss_individual_sync_result(task_id=task_id, user_id=current_user.id)
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
    can_manage_secret_reveal = current_user.has_permission(
        'kubernetes_secrets.manage_reveal'
    )

    if form.validate_on_submit():
        kube_file = form.kubeconfig.data

        if kube_file is None:
            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_create',
                status='error',
                title='Cluster could not be added',
                message='Kubeconfig file is required.',
                detail='Select a valid kubeconfig file before saving the cluster registration.',
                action_url=url_for('cluster.add_cluster'),
                action_label='Review cluster form',
                action_icon='server-cog',
                metadata={
                    'cluster_name': form.name.data or '-',
                    'environment': form.environment.data or '-',
                    'reason': 'missing_kubeconfig',
                },
                queue_feedback=True,
            )

            return render_template(
                'cluster/add.html',
                form=form,
                can_manage_secret_reveal=can_manage_secret_reveal,
            )

        try:
            kube_content = kube_file.read().decode(
                'utf-8',
            )

            assert form.name.data is not None
            assert form.environment.data is not None
            assert form.kubeconfig.data is not None

            reveal_kubeconfig = None
            if can_manage_secret_reveal:
                reveal_file = form.secret_reveal_kubeconfig.data
                if reveal_file is not None and getattr(reveal_file, 'filename', ''):
                    reveal_kubeconfig = reveal_file.read().decode('utf-8')

            cluster = create_cluster(
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
                secret_reveal_policy=(
                    form.secret_reveal_policy.data or 'disabled'
                    if can_manage_secret_reveal
                    else 'disabled'
                ),
                secret_reveal_kubeconfig=reveal_kubeconfig,
                secret_reveal_encryption_verified=(
                    bool(form.secret_reveal_encryption_verified.data)
                    if can_manage_secret_reveal
                    else False
                ),
                secret_reveal_audit_verified=(
                    bool(form.secret_reveal_audit_verified.data)
                    if can_manage_secret_reveal
                    else False
                ),
            )

            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_create',
                status='success',
                title='Cluster added',
                message=f'{cluster.name} is now registered in KAORI.',
                detail='The cluster is ready for connection testing, inventory synchronization, and observability integration setup.',
                action_url=url_for('cluster.list_clusters'),
                action_label='View clusters',
                action_icon='server',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'environment': cluster.environment,
                    'server': cluster.server,
                    'secret_reveal_policy': cluster.secret_reveal_policy,
                    'secret_reveal_credential_configured': bool(cluster.secret_reveal_kubeconfig),
                },
                queue_feedback=True,
            )

            return redirect(
                url_for(
                    'cluster.list_clusters',
                )
            )

        except ValueError as exc:
            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_create',
                status='error',
                title='Cluster could not be added',
                message=str(exc),
                detail='Review the cluster name and kubeconfig content, then submit the form again.',
                action_url=url_for('cluster.add_cluster'),
                action_label='Review cluster form',
                action_icon='server-cog',
                metadata={
                    'cluster_name': form.name.data or '-',
                    'environment': form.environment.data or '-',
                    'reason': type(exc).__name__,
                },
                queue_feedback=True,
            )
        except Exception as exc:
            logger.exception(
                'Cluster creation failed for submitted name %s.',
                form.name.data,
            )
            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_create',
                status='error',
                title='Cluster could not be added',
                message='KAORI could not save the cluster registration.',
                detail='Review the application logs and database connectivity before retrying the operation.',
                action_url=url_for('cluster.add_cluster'),
                action_label='Review cluster form',
                action_icon='server-cog',
                metadata={
                    'cluster_name': form.name.data or '-',
                    'environment': form.environment.data or '-',
                    'reason': type(exc).__name__,
                },
                queue_feedback=True,
            )

    if request.method == 'POST' and form.errors:
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_create',
            status='warning',
            title='Cluster registration needs attention',
            message='The submitted cluster form contains validation errors.',
            detail='Correct the highlighted fields and attach a valid kubeconfig before saving again.',
            action_url=url_for('cluster.add_cluster'),
            action_label='Review cluster form',
            action_icon='server-cog',
            metadata={
                'cluster_name': form.name.data or '-',
                'environment': form.environment.data or '-',
                'validation_fields': sorted(form.errors.keys()),
            },
            queue_feedback=True,
        )

    return render_template(
        'cluster/add.html',
        form=form,
        can_manage_secret_reveal=can_manage_secret_reveal,
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
    try:
        result = run_test_cluster(
            cluster,
        )
    except Exception:
        logger.exception(
            'Cluster connection test failed unexpectedly for %s.',
            cluster.id,
        )
        result = {
            'success': False,
            'error': (
                'KAORI could not complete the Kubernetes API connection test. '
                'Review the cluster endpoint, kubeconfig credentials, TLS settings, and application logs.'
            ),
            'reason': 'Connection test could not complete',
            'failure_code': 'unexpected_error',
            'endpoint_host': None,
            'endpoint_port': None,
            'request_path': '/api/v1/nodes',
        }

    if result['success']:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_connection_test',
            status='success',
            title='Cluster connection verified',
            message=f'KAORI connected to {cluster.name} successfully.',
            detail=f'Kubernetes API access is available and {result.get("node_count", 0)} node(s) were reported.',
            action_url=url_for('cluster.list_clusters'),
            action_label='View clusters',
            action_icon='server',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'node_count': result.get('node_count', 0),
                'server': cluster.server,
            },
        )
    else:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_connection_test',
            status='error',
            title='Cluster connection failed',
            message=f'KAORI could not connect to {cluster.name}.',
            detail=result.get('error') or 'Review Kubernetes API access, kubeconfig credentials, and TLS settings.',
            action_url=url_for('cluster.edit_cluster', cluster_id=cluster.id),
            action_label='Review cluster settings',
            action_icon='settings-2',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'server': cluster.server,
                'reason': result.get('reason') or 'Connection failed',
                'failure_code': result.get('failure_code') or 'connection_failed',
                'endpoint_host': result.get('endpoint_host'),
                'endpoint_port': result.get('endpoint_port'),
                'request_path': result.get('request_path') or '/api/v1/nodes',
            },
        )

    if request.headers.get('HX-Request') == 'true':
        table_html = render_template(
            'cluster/partials/_table.html',
            **_build_cluster_context_from_request(),
        )
        return f'{table_html}{_render_operational_toast(feedback, toast_oob=True)}'

    queue_quick_action_feedback(feedback)
    return redirect(request.referrer or url_for('cluster.list_clusters'))


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
    can_manage_secret_reveal = current_user.has_permission(
        'kubernetes_secrets.manage_reveal'
    )

    if form.validate_on_submit():
        name = form.name.data
        environment = form.environment.data

        assert name is not None
        assert environment is not None

        try:
            previous_name = cluster.name
            previous_environment = cluster.environment
            previous_reveal_policy = cluster.secret_reveal_policy
            reveal_kubeconfig = None
            if can_manage_secret_reveal:
                reveal_file = form.secret_reveal_kubeconfig.data
                if reveal_file is not None and getattr(reveal_file, 'filename', ''):
                    reveal_kubeconfig = reveal_file.read().decode('utf-8')

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
                secret_reveal_policy=(
                    form.secret_reveal_policy.data or 'disabled'
                    if can_manage_secret_reveal
                    else cluster.secret_reveal_policy
                ),
                secret_reveal_kubeconfig=reveal_kubeconfig,
                secret_reveal_encryption_verified=(
                    bool(form.secret_reveal_encryption_verified.data)
                    if can_manage_secret_reveal
                    else cluster.secret_reveal_encryption_verified
                ),
                secret_reveal_audit_verified=(
                    bool(form.secret_reveal_audit_verified.data)
                    if can_manage_secret_reveal
                    else cluster.secret_reveal_audit_verified
                ),
                remove_secret_reveal_kubeconfig=(
                    bool(form.secret_reveal_remove_kubeconfig.data)
                    if can_manage_secret_reveal
                    else False
                ),
            )

            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_update',
                status='success',
                title='Cluster updated',
                message=f'{cluster.name} configuration was updated successfully.',
                detail='Cluster identity, Kubernetes API TLS settings, and Protected Secret Reveal controls now use the saved values.',
                action_url=url_for('cluster.list_clusters'),
                action_label='View clusters',
                action_icon='server',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'previous_name': previous_name,
                    'environment': cluster.environment,
                    'previous_environment': previous_environment,
                    'verify_ssl': cluster.kube_verify_ssl,
                    'allow_weak_tls': cluster.kube_allow_weak_tls,
                    'secret_reveal_policy': cluster.secret_reveal_policy,
                    'previous_secret_reveal_policy': previous_reveal_policy,
                    'secret_reveal_credential_configured': bool(cluster.secret_reveal_kubeconfig),
                    'secret_reveal_encryption_verified': cluster.secret_reveal_encryption_verified,
                    'secret_reveal_audit_verified': cluster.secret_reveal_audit_verified,
                },
                queue_feedback=True,
            )

            return redirect(
                url_for(
                    'cluster.list_clusters',
                )
            )

        except ValueError as exc:
            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_update',
                status='error',
                title='Cluster update failed',
                message=str(exc),
                detail='Review the cluster name and submitted configuration before saving again.',
                action_url=url_for('cluster.edit_cluster', cluster_id=cluster.id),
                action_label='Review cluster settings',
                action_icon='settings-2',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'submitted_name': name,
                    'submitted_environment': environment,
                    'reason': type(exc).__name__,
                },
                queue_feedback=True,
            )
        except Exception as exc:
            logger.exception(
                'Cluster update failed for %s.',
                cluster.id,
            )
            record_operational_activity(
                user_id=current_user.id,
                event_type='cluster_update',
                status='error',
                title='Cluster update failed',
                message=f'{cluster.name} configuration could not be saved.',
                detail='Review application logs and database connectivity before retrying the update.',
                action_url=url_for('cluster.edit_cluster', cluster_id=cluster.id),
                action_label='Review cluster settings',
                action_icon='settings-2',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'submitted_name': name,
                    'submitted_environment': environment,
                    'reason': type(exc).__name__,
                },
                queue_feedback=True,
            )

    if request.method == 'POST' and form.errors:
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_update',
            status='warning',
            title='Cluster update needs attention',
            message='The submitted cluster form contains validation errors.',
            detail='Correct the highlighted fields before saving the cluster configuration again.',
            action_url=url_for('cluster.edit_cluster', cluster_id=cluster.id),
            action_label='Review cluster settings',
            action_icon='settings-2',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'validation_fields': sorted(form.errors.keys()),
            },
            queue_feedback=True,
        )

    return render_template(
        'cluster/edit.html',
        form=form,
        cluster=cluster,
        can_manage_secret_reveal=can_manage_secret_reveal,
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

    cluster_name = cluster.name
    cluster_environment = cluster.environment
    cluster_server = cluster.server

    try:
        delete_cluster(
            cluster,
        )
    except Exception as exc:
        logger.exception(
            'Cluster deletion failed for %s.',
            cluster_id,
        )
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_delete',
            status='error',
            title='Cluster deletion failed',
            message=f'{cluster_name} could not be deleted.',
            detail='The database rejected the delete operation. Review dependent records and application logs before retrying.',
            action_url=url_for('cluster.list_clusters'),
            action_label='View clusters',
            action_icon='server',
            metadata={
                'cluster_id': cluster_id,
                'cluster_name': cluster_name,
                'reason': type(exc).__name__,
            },
            queue_feedback=True,
        )
    else:
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_delete',
            status='success',
            title='Cluster deleted',
            message=f'{cluster_name} was removed from KAORI.',
            detail='Stored cluster registration, inventory, and associated observability configuration were removed according to database relationships.',
            action_url=url_for('cluster.list_clusters'),
            action_label='View clusters',
            action_icon='server',
            metadata={
                'cluster_id': cluster_id,
                'cluster_name': cluster_name,
                'environment': cluster_environment,
                'server': cluster_server,
            },
            queue_feedback=True,
        )

    return redirect(
        url_for(
            'cluster.list_clusters',
        )
    )
