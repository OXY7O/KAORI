"""Kubernetes provider orchestration routes under the shared Integrations blueprint."""

from flask import abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.access.rbac.decorators import permission_required
from app.common.http import is_htmx_request
from app.integrations.orchestration.container_orchestrator.frontpage import (
    KubernetesCoverageFilters,
    KubernetesFrontPageFilters,
    KubernetesRegistryFilters,
    build_kubernetes_page,
    build_kubernetes_registry_row,
)
from app.integrations.orchestration.container_orchestrator.tenant_capsule_web import capsule_rbac_operation
from app.integrations.repository import get_kubernetes_connection_by_cluster_id
from app.integrations.route_common import integrations_bp
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.service import build_kubernetes_capability_registry, build_kubernetes_detail
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
    validation_poll_response,
)
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)


@integrations_bp.get('/kubernetes')
@permission_required('integrations.manage')
def kubernetes() -> ResponseReturnValue:
    context = build_kubernetes_page(
        KubernetesFrontPageFilters(
            registry=KubernetesRegistryFilters(
                query=request.args.get('q', '').strip(),
                environment=request.args.get('environment', '').strip(),
                readiness=request.args.get('readiness', '').strip(),
                coverage=request.args.get('coverage', '').strip(),
                page=request.args.get('page', 1, type=int) or 1,
                per_page=request.args.get('per_page', 5, type=int) or 5,
            ),
            coverage=KubernetesCoverageFilters(
                query=request.args.get('coverage_q', '').strip(),
                environment=request.args.get('coverage_environment', '').strip(),
                status=request.args.get('coverage_status', '').strip(),
                page=request.args.get('coverage_page', 1, type=int) or 1,
                per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
            ),
        )
    )
    requested_tab = request.args.get('tab', 'coverage').strip()
    context['active_tab'] = requested_tab if requested_tab in {'coverage', 'registry'} else 'coverage'
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'kubernetes-integration-coverage':
            return render_template(
                'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_integration_coverage.html',
                **context,
            )
        if target == 'kubernetes-connection-registry':
            return render_template(
                'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html',
                **context,
            )
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html', **context
    )


def _kubernetes_detail_context(
    cluster_id: str,
    *,
    include_history: bool = False,
    history_page: int | None = None,
    history_per_page: int | None = None,
) -> dict[str, object]:
    context = build_kubernetes_detail(
        cluster_id,
        binding_page=request.args.get('binding_page', 1, type=int) or 1,
        binding_per_page=request.args.get('binding_per_page', 5, type=int) or 5,
    )
    if context is None:
        abort(404)
    connection = context['connection']
    capability_task_id = get_active_validation_task_id(
        integration_type='container_orchestrator',
        operation='full_validation',
        integration_instance_id=connection.integration_instance_id,
    )
    runtime_task_id = get_active_validation_task_id(
        integration_type='container_orchestrator',
        operation='runtime_refresh',
        integration_instance_id=connection.integration_instance_id,
    )
    context['capability_validation_job'] = build_validation_snapshot(capability_task_id) if capability_task_id else None
    context['runtime_validation_job'] = build_validation_snapshot(runtime_task_id) if runtime_task_id else None
    context['capsule_rbac_bootstrap'] = capsule_rbac_operation('latest_capsule_role_bootstrap_evidence')(cluster_id)
    context['capability_registry'] = build_kubernetes_capability_registry(
        context['feature_rows'],
        query=request.args.get('capability_q', '').strip(),
        requirement=request.args.get('capability_requirement', '').strip(),
        status=request.args.get('capability_status', '').strip(),
        page=request.args.get('capability_page', 1, type=int) or 1,
        per_page=request.args.get('capability_per_page', 5, type=int) or 5,
    )
    if include_history:
        resolved_page = history_page if history_page is not None else (request.args.get('page', 1, type=int) or 1)
        resolved_per_page = (
            history_per_page if history_per_page is not None else (request.args.get('per_page', 5, type=int) or 5)
        )
        rows, pagination = paginate_runtime_history(
            'container_orchestrator',
            str(connection.id),
            page=resolved_page,
            per_page=resolved_per_page,
            trigger_type=request.args.get('history_trigger', '').strip(),
            health_status=request.args.get('history_health', '').strip(),
            readiness=request.args.get('history_readiness', '').strip(),
        )
        context['history'] = runtime_history_view(rows, pagination=pagination)
    return context


@integrations_bp.get('/kubernetes/<string:cluster_id>/bindings/registry')
@permission_required('clusters.view')
def kubernetes_binding_registry(cluster_id: str) -> ResponseReturnValue:
    context = _kubernetes_detail_context(cluster_id)
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_binding_registry.html',
        **context,
    )


@integrations_bp.get('/kubernetes/<string:cluster_id>/registry-details')
@permission_required('integrations.manage')
def kubernetes_registry_details(cluster_id: str) -> ResponseReturnValue:
    row = build_kubernetes_registry_row(cluster_id)
    if row is None:
        abort(404)
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry_detail_content.html',
        row=row,
    )


@integrations_bp.get('/kubernetes/<string:cluster_id>')
@permission_required('clusters.view')
def kubernetes_detail(cluster_id: str) -> ResponseReturnValue:
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html',
        **_kubernetes_detail_context(cluster_id, include_history=True),
    )


def _capsule_rbac_feedback_response(
    cluster_id: str,
    result: dict[str, object],
    *,
    operation: str,
) -> ResponseReturnValue:
    """Present committed Capsule RBAC evidence using the canonical KAORI feedback channel."""
    provider_status = str(result.get('status') or 'failed')
    if operation == 'check':
        summary = {
            'ready': (
                'Capsule RBAC check complete',
                'All four canonical ClusterRoles match their approved Access Profiles.',
            ),
            'missing': (
                'Capsule RBAC prerequisites missing',
                'One or more canonical ClusterRoles are missing; review the evidence before approved bootstrap.',
            ),
            'conflict': (
                'Capsule RBAC role conflict',
                'Existing ClusterRoles conflict with the approved profiles; no roles were changed.',
            ),
        }
        title, message = summary.get(
            provider_status,
            ('Capsule RBAC check failed', 'ClusterRole inspection did not complete; review the committed evidence.'),
        )
    else:
        title, message = (
            (
                'Capsule ClusterRole bootstrap verified',
                'Missing canonical ClusterRoles were created and verified.',
            )
            if provider_status == 'ready'
            else (
                'Capsule ClusterRole bootstrap needs attention',
                'ClusterRole bootstrap did not verify as Ready; inspect committed evidence before retrying.',
            )
        )
    feedback_status = (
        'success' if provider_status == 'ready' else 'warning' if provider_status == 'missing' else 'error'
    )
    destination = url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation'
    is_htmx = is_htmx_request()
    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type=f'kubernetes_capsule_rbac_{operation}',
        status=feedback_status,
        title=title,
        message=message,
        detail=(
            'ClusterRole inspection and bootstrap evidence is committed separately. '
            'Capsule controller bindings and effective Access Grants remain independent.'
        ),
        action_url=destination,
        action_label='Review Capsule RBAC evidence',
        action_icon='shield-check',
        metadata={
            'cluster_id': cluster_id,
            'operation': operation,
            'provider_status': provider_status,
            'ready': result.get('ready'),
            'missing': result.get('missing'),
            'conflict': result.get('conflict'),
            'source': 'capsule_cluster_rbac',
        },
        queue_feedback=not is_htmx,
        delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE,
    )
    if is_htmx:
        context = _kubernetes_detail_context(cluster_id)
        context.update(
            {
                'operation_feedback': feedback,
                'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
            }
        )
        return render_template(
            'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capsule_rbac_bootstrap.html',
            **context,
        )
    return redirect(destination)


@integrations_bp.post('/kubernetes/<string:cluster_id>/capsule-rbac/check')
@permission_required('clusters.sync')
def kubernetes_capsule_rbac_check(cluster_id: str) -> ResponseReturnValue:
    if get_kubernetes_connection_by_cluster_id(cluster_id) is None:
        abort(404)
    try:
        validate_csrf(str(request.form.get('csrf_token') or ''))
    except ValidationError:
        abort(400)
    result = capsule_rbac_operation('check_capsule_role_bootstrap')(cluster_id, int(current_user.id))
    return _capsule_rbac_feedback_response(cluster_id, result, operation='check')


@integrations_bp.post('/kubernetes/<string:cluster_id>/capsule-rbac/bootstrap')
@permission_required('clusters.manage')
@permission_required('integrations.manage')
def kubernetes_capsule_rbac_bootstrap(cluster_id: str) -> ResponseReturnValue:
    if get_kubernetes_connection_by_cluster_id(cluster_id) is None:
        abort(404)
    try:
        validate_csrf(str(request.form.get('csrf_token') or ''))
    except ValidationError:
        abort(400)
    if request.form.get('confirm_cluster_rbac') != 'approved':
        abort(400)
    result = capsule_rbac_operation('bootstrap_missing_capsule_roles')(cluster_id, int(current_user.id), approved=True)
    return _capsule_rbac_feedback_response(cluster_id, result, operation='bootstrap')


@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/registry')
@permission_required('clusters.view')
def kubernetes_capability_registry(cluster_id: str) -> ResponseReturnValue:
    context = _kubernetes_detail_context(cluster_id)
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html',
        validation_job=context.get('capability_validation_job'),
        **context,
    )


@integrations_bp.post('/kubernetes/<string:cluster_id>/capabilities/validate')
@permission_required('clusters.sync')
def kubernetes_capability_validate(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        validation_job, created = enqueue_instance_validation(
            integration_type='container_orchestrator',
            integration_instance_id=connection.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_capability_validation_queued'
            if created
            else 'kubernetes_capability_validation_already_running',
            status='info' if created else 'warning',
            title='Kubernetes capability validation queued' if created else 'Kubernetes validation already running',
            message=(
                f'KAORI queued full capability validation for {connection.cluster.name}.'
                if created
                else f'A Kubernetes validation job is already running for {connection.cluster.name}.'
            ),
            detail=(
                'The dedicated validation worker will discover served APIs, effective RBAC, stable adapters, and fallback requirements.'
                if created
                else 'KAORI retained the active worker task and did not enqueue a duplicate validation job.'
            ),
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation',
            action_label='Review capability validation',
            action_icon='scan-search',
            metadata={
                'task_id': validation_job.get('task_id'),
                'cluster_id': cluster_id,
                'connection_id': connection.id,
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_capability_validation_enqueue_failed',
            status='error',
            title='Kubernetes capability validation not queued',
            message=f'KAORI could not queue capability validation for {connection.cluster.name}.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation',
            action_label='Review capability validation',
            action_icon='scan-search',
            metadata={'cluster_id': cluster_id, 'connection_id': connection.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        context = _kubernetes_detail_context(cluster_id)
        context.update(
            {
                'validation_job': validation_job,
                'capability_validation_job': validation_job,
                'operation_feedback': feedback,
                'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
            }
        )
        return render_template(
            'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html',
            **context,
        )
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation')


@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/validate/status/<string:task_id>')
@permission_required('clusters.view')
def kubernetes_capability_validation_status(cluster_id: str, task_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='container_orchestrator',
        integration_instance_id=connection.integration_instance_id,
    ):
        abort(404)
    context = _kubernetes_detail_context(cluster_id)
    context.update(
        {
            'validation_job': snapshot,
            'capability_validation_job': snapshot,
            'operation_feedback': snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
            'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
            'runtime_history_oob': True,
        }
    )
    content = render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html',
        **context,
    )
    return validation_poll_response(content, snapshot=snapshot)


@integrations_bp.post('/kubernetes/<string:cluster_id>/runtime/refresh')
@permission_required('clusters.sync')
def kubernetes_runtime_refresh(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        validation_job, created = enqueue_runtime_health_refresh(
            integration_type='container_orchestrator',
            integration_instance_id=connection.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_runtime_refresh_queued' if created else 'kubernetes_runtime_refresh_already_running',
            status='info' if created else 'warning',
            title='Kubernetes runtime refresh queued' if created else 'Kubernetes runtime refresh already running',
            message=(
                f'KAORI queued a lightweight runtime health refresh for {connection.cluster.name}.'
                if created
                else f'A validation or runtime refresh is already running for {connection.cluster.name}.'
            ),
            detail=(
                'The dedicated runtime worker will check reachability and runtime health while preserving full capability evidence.'
                if created
                else 'KAORI kept the existing task and did not enqueue a duplicate validation job.'
            ),
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime',
            action_label='Review Kubernetes runtime',
            action_icon='activity',
            metadata={
                'task_id': validation_job.get('task_id'),
                'cluster_id': cluster_id,
                'connection_id': connection.id,
                'queue': current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_runtime_refresh_enqueue_failed',
            status='error',
            title='Kubernetes runtime refresh not queued',
            message=f'KAORI could not queue runtime health refresh for {connection.cluster.name}.',
            detail='Verify Redis, the Celery broker, and the integration-runtime worker before retrying.',
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime',
            action_label='Review Kubernetes runtime',
            action_icon='activity',
            metadata={'cluster_id': cluster_id, 'connection_id': connection.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        context = _kubernetes_detail_context(cluster_id, include_history=True)
        context.update(
            {
                'validation_job': validation_job,
                'runtime_validation_job': validation_job,
                'operation_feedback': feedback,
                'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
                'runtime_history_oob': True,
            }
        )
        return render_template(
            'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html',
            **context,
        )
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime')


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/refresh/status/<string:task_id>')
@permission_required('clusters.view')
def kubernetes_runtime_refresh_status(cluster_id: str, task_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='container_orchestrator',
        integration_instance_id=connection.integration_instance_id,
    ):
        abort(404)
    context = _kubernetes_detail_context(cluster_id, include_history=True)
    context.update(
        {
            'validation_job': snapshot,
            'runtime_validation_job': snapshot,
            'operation_feedback': snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
            'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
        }
    )
    content = render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html',
        **context,
    )
    return validation_poll_response(content, snapshot=snapshot)


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/history')
@permission_required('clusters.view')
def kubernetes_runtime_history(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    rows, pagination = paginate_runtime_history(
        'container_orchestrator',
        str(connection.id),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
        trigger_type=request.args.get('history_trigger', '').strip(),
        health_status=request.args.get('history_health', '').strip(),
        readiness=request.args.get('history_readiness', '').strip(),
    )
    return render_template(
        'integrations/partials/_runtime_history.html',
        runtime_history=runtime_history_view(rows, pagination=pagination),
        runtime_history_id='kubernetes-runtime-history',
        runtime_history_loading_id='kubernetes-history-loading',
        runtime_history_url=url_for('integrations.kubernetes_runtime_history', cluster_id=cluster_id),
        runtime_history_endpoint='integrations.kubernetes_runtime_history',
        runtime_history_route_args={'cluster_id': cluster_id},
        runtime_history_detail_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id),
        runtime_history_detail_endpoint='integrations.kubernetes_detail',
        runtime_history_filters_enabled=True,
        provider_label='Kubernetes',
    )
