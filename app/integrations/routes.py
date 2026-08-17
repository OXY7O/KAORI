from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.common.http import htmx_target, is_htmx_request
from app.integrations.binding_service import SourceBindingSpec, create_source_binding
from app.integrations.coverage import build_binding_workspace
from app.integrations.domain_service import build_integration_domain_page
from app.integrations.kubernetes_frontpage import (
    KubernetesCoverageFilters,
    KubernetesFrontPageFilters,
    KubernetesRegistryFilters,
    build_kubernetes_page,
    build_kubernetes_registry_row,
)
from app.integrations.overview_workspace import build_integrations_overview
from app.integrations.repository import get_cluster, get_kubernetes_connection_by_cluster_id
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.service import (
    build_alertmanager_page,
    build_integration_runtime_detail,
    build_kubernetes_capability_registry,
    build_kubernetes_detail,
    build_prometheus_page,
)
from app.integrations.validation.state import (
    build_validation_snapshot,
    get_active_validation_task_id,
)
from app.integrations.validation.web import (
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
)
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.rbac.decorators import permission_required

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')


@integrations_bp.get('/')
@permission_required('settings.manage_integrations')
def overview() -> ResponseReturnValue:
    context = build_integrations_overview(
        tab=request.args.get('tab', 'catalog').strip(),
        provider=request.args.get('provider', '').strip(),
        health=request.args.get('health', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    is_runtime_partial = (
        is_htmx_request() and htmx_target() == 'integration-runtime-overview' and context['active_tab'] == 'runtime'
    )
    if is_runtime_partial:
        return render_template('integrations/partials/_runtime_overview.html', **context)
    return render_template('integrations/overview.html', **context)


def _render_domain_page(domain_key: str) -> ResponseReturnValue:
    return render_template(
        'integrations/domain.html',
        **build_integration_domain_page(
            domain_key,
            active_tab=request.args.get('tab', 'registry').strip(),
            provider_page=request.args.get('provider_page', 1, type=int) or 1,
            provider_per_page=request.args.get('provider_per_page', 5, type=int) or 5,
            binding_page=request.args.get('binding_page', 1, type=int) or 1,
            binding_per_page=request.args.get('binding_per_page', 5, type=int) or 5,
        ),
    )


@integrations_bp.get('/orchestration')
@permission_required('settings.manage_integrations')
def orchestration() -> ResponseReturnValue:
    return _render_domain_page('orchestration')


@integrations_bp.get('/observability')
@permission_required('settings.manage_integrations')
def observability() -> ResponseReturnValue:
    return _render_domain_page('observability')


@integrations_bp.get('/storage')
@permission_required('settings.manage_integrations')
def storage() -> ResponseReturnValue:
    return _render_domain_page('storage')


@integrations_bp.get('/runtime/<string:detail_key>/details')
@permission_required('settings.manage_integrations')
def runtime_overview_details(detail_key: str) -> ResponseReturnValue:
    provider, separator, instance_id = detail_key.partition(':')
    if not separator or not provider or not instance_id:
        abort(404)
    detail = build_integration_runtime_detail(provider, instance_id)
    if detail is None:
        abort(404)
    return render_template(
        'integrations/partials/_runtime_overview_modal.html',
        detail=detail,
    )


@integrations_bp.get('/kubernetes')
@permission_required('settings.manage_integrations')
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
            return render_template('integrations/kubernetes/partials/_integration_coverage.html', **context)
        if target == 'kubernetes-connection-registry':
            return render_template('integrations/kubernetes/partials/_registry.html', **context)
    return render_template('integrations/kubernetes.html', **context)


def _kubernetes_detail_context(
    cluster_id: str,
    *,
    include_history: bool = False,
    history_page: int | None = None,
    history_per_page: int | None = None,
) -> dict[str, object]:
    context = build_kubernetes_detail(cluster_id)
    if context is None:
        abort(404)
    connection = context['connection']
    capability_task_id = get_active_validation_task_id(
        provider_type='kubernetes',
        operation='full_validation',
        instance_id=connection.id,
    )
    runtime_task_id = get_active_validation_task_id(
        provider_type='kubernetes',
        operation='runtime_refresh',
        instance_id=connection.id,
    )
    context['capability_validation_job'] = build_validation_snapshot(capability_task_id) if capability_task_id else None
    context['runtime_validation_job'] = build_validation_snapshot(runtime_task_id) if runtime_task_id else None
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
            'kubernetes',
            str(connection.id),
            page=resolved_page,
            per_page=resolved_per_page,
            trigger_type=request.args.get('history_trigger', '').strip(),
            health_status=request.args.get('history_health', '').strip(),
            readiness=request.args.get('history_readiness', '').strip(),
        )
        context['history'] = runtime_history_view(rows, pagination=pagination)
    return context


@integrations_bp.get('/kubernetes/<string:cluster_id>/registry-details')
@permission_required('settings.manage_integrations')
def kubernetes_registry_details(cluster_id: str) -> ResponseReturnValue:
    row = build_kubernetes_registry_row(cluster_id)
    if row is None:
        abort(404)
    return render_template(
        'integrations/kubernetes/partials/_registry_detail_content.html',
        row=row,
    )


@integrations_bp.get('/kubernetes/<string:cluster_id>')
@permission_required('clusters.view')
def kubernetes_detail(cluster_id: str) -> ResponseReturnValue:
    return render_template(
        'integrations/kubernetes/detail.html',
        **_kubernetes_detail_context(cluster_id, include_history=True),
    )


@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/registry')
@permission_required('clusters.view')
def kubernetes_capability_registry(cluster_id: str) -> ResponseReturnValue:
    context = _kubernetes_detail_context(cluster_id)
    return render_template(
        'integrations/kubernetes/partials/_capability_registry.html',
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
            provider_type='kubernetes',
            instance_id=connection.id,
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
        return render_template('integrations/kubernetes/partials/_capability_workspace.html', **context)
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
        provider_type='kubernetes',
        instance_id=connection.id,
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
    return render_template('integrations/kubernetes/partials/_capability_workspace.html', **context)


@integrations_bp.post('/kubernetes/<string:cluster_id>/runtime/refresh')
@permission_required('clusters.sync')
def kubernetes_runtime_refresh(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        validation_job, created = enqueue_runtime_health_refresh(
            provider_type='kubernetes',
            instance_id=connection.id,
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
        return render_template('integrations/kubernetes/partials/_runtime_workspace.html', **context)
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
        provider_type='kubernetes',
        instance_id=connection.id,
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
    return render_template('integrations/kubernetes/partials/_runtime_workspace.html', **context)


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/history')
@permission_required('clusters.view')
def kubernetes_runtime_history(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    rows, pagination = paginate_runtime_history(
        'kubernetes',
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


@integrations_bp.get('/prometheus')
@permission_required('settings.manage_integrations')
def prometheus() -> ResponseReturnValue:
    context = build_prometheus_page(
        query=request.args.get('q', '').strip(),
        compatibility=request.args.get('compatibility', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        tab=request.args.get('tab', 'coverage').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
        coverage_query=request.args.get('coverage_q', '').strip(),
        coverage_environment=request.args.get('coverage_environment', '').strip(),
        coverage_status=request.args.get('coverage_status', '').strip(),
        coverage_page=request.args.get('coverage_page', 1, type=int) or 1,
        coverage_per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'integration-coverage':
            return render_template('integrations/partials/_coverage_card.html', **context)
        if target == 'prometheus-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        if target == 'prometheus-inventory-card':
            return render_template('integrations/prometheus/partials/_instance_inventory.html', **context)
        return render_template('integrations/prometheus/partials/_inventory_content.html', **context)
    return render_template('integrations/prometheus.html', **context)


@integrations_bp.get('/alertmanager')
@permission_required('settings.manage_integrations')
def alertmanager() -> ResponseReturnValue:
    context = build_alertmanager_page(
        query=request.args.get('q', '').strip(),
        compatibility=request.args.get('compatibility', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        deployment_type=request.args.get('deployment_type', '').strip(),
        tab=request.args.get('tab', 'coverage').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
        coverage_query=request.args.get('coverage_q', '').strip(),
        coverage_environment=request.args.get('coverage_environment', '').strip(),
        coverage_status=request.args.get('coverage_status', '').strip(),
        coverage_page=request.args.get('coverage_page', 1, type=int) or 1,
        coverage_per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'integration-coverage':
            return render_template('integrations/partials/_coverage_card.html', **context)
        if target == 'alertmanager-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        if target == 'alertmanager-inventory-card':
            return render_template('integrations/alertmanager/partials/_inventory_card.html', **context)
        return render_template('integrations/alertmanager/partials/_inventory_content.html', **context)
    return render_template('integrations/alertmanager.html', **context)


def _binding_response(provider_type: str, *, scope_key: str) -> ResponseReturnValue:
    submitted = dict(request.form) if request.method == 'POST' else {}
    feedback = None

    if request.method == 'POST':
        source_id = request.form.get('source_id', type=int)
        cluster_id = request.form.get('scope_key', scope_key).strip()
        selector_label = request.form.get('selector_label', '').strip()
        selector_value = request.form.get('selector_value', '').strip()
        selector_operator = request.form.get('selector_operator', '=').strip() or '='
        role = request.form.get('binding_role', 'primary').strip().lower()
        priority = request.form.get('priority', 100, type=int) or 100
        source = None
        cluster = None
        binding = None
        try:
            if source_id is None:
                raise ValueError(f'Select an existing {provider_type.title()} source.')
            cluster = get_cluster(cluster_id)
            if cluster is None:
                raise ValueError('The selected Kubernetes scope no longer exists.')
            created_binding = create_source_binding(
                provider_type,
                source_id=source_id,
                spec=SourceBindingSpec(
                    asset_type='kubernetes_cluster',
                    asset_key=str(cluster.id),
                    role=role,
                    priority=priority,
                    selector_label=selector_label,
                    selector_value=selector_value,
                    selector_operator=selector_operator,
                ),
                asset=cluster,
            )
            source = created_binding.source
            cluster = created_binding.asset
            binding = created_binding.binding
            if source is None or cluster is None or binding is None:
                raise ValueError('KAORI could not resolve the saved source binding context.')
        except ValueError as exc:
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type=f'{provider_type}_binding_create_rejected',
                status='error',
                title=f'{provider_type.title()} binding not saved',
                message='KAORI could not create the requested source binding.',
                detail=str(exc),
                action_url=request.path,
                action_label='Review binding',
                action_icon='link-2',
                metadata={
                    'provider_type': provider_type,
                    'scope_type': 'kubernetes_cluster',
                    'scope_key': cluster_id,
                    'source_id': source_id,
                    'selector_label': selector_label or None,
                },
                queue_feedback=not is_htmx_request(),
            )
        except Exception as exc:
            current_app.logger.exception(
                'Unexpected %s binding persistence failure for scope %s and source %s',
                provider_type,
                cluster_id,
                source_id,
            )
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type=f'{provider_type}_binding_create_failed',
                status='error',
                title=f'{provider_type.title()} binding not saved',
                message='KAORI could not persist the source binding.',
                detail='Review KAORI logs and database connectivity before retrying.',
                action_url=request.path,
                action_label='Review binding',
                action_icon='link-2',
                metadata={
                    'provider_type': provider_type,
                    'scope_key': cluster_id,
                    'source_id': source_id,
                    'reason': type(exc).__name__,
                },
                queue_feedback=not is_htmx_request(),
            )
        else:
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type=f'{provider_type}_binding_created',
                status='success',
                title=f'{provider_type.title()} binding saved',
                message=f'{source.name} is associated with {cluster.name} and requires binding validation.',
                detail=f'Binding selector: {selector_label}={selector_value}. Source credentials and runtime remain shared; operational resolution stays blocked until validation succeeds.',
                action_url=(
                    url_for('prometheus.instance_detail', instance_id=source.id) + '#scope'
                    if provider_type == 'prometheus'
                    else url_for('alertmanager.instance_detail', instance_id=source.id) + '#scope'
                ),
                action_label='Review source binding',
                action_icon='route',
                metadata={
                    'provider_type': provider_type,
                    'binding_id': binding.id,
                    'scope_key': cluster.id,
                    'source_id': source.id,
                    'selector_label': selector_label,
                    'selector_value': selector_value,
                },
                queue_feedback=not is_htmx_request(),
            )
            if not is_htmx_request():
                return redirect(
                    url_for('integrations.prometheus' if provider_type == 'prometheus' else 'integrations.alertmanager')
                    + '#integration-coverage'
                )

    context = build_binding_workspace(
        provider_type,
        scope_key=scope_key,
        submitted=submitted,
        operation_feedback=feedback,
    )
    if context['cluster'] is None and request.method == 'GET':
        abort(404)
    context['notification_context'] = (
        get_navigation_notification_context(user_id=int(current_user.id)) if feedback is not None else None
    )
    if is_htmx_request():
        return render_template('integrations/bindings/partials/_workspace.html', **context)
    return render_template('integrations/bindings/source.html', **context)


@integrations_bp.route('/prometheus/bind', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def bind_prometheus_source() -> ResponseReturnValue:
    scope_key = request.values.get('scope_key', '').strip()
    if not scope_key:
        abort(400)
    return _binding_response('prometheus', scope_key=scope_key)


@integrations_bp.route('/alertmanager/bind', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def bind_alertmanager_source() -> ResponseReturnValue:
    scope_key = request.values.get('scope_key', '').strip()
    if not scope_key:
        abort(400)
    return _binding_response('alertmanager', scope_key=scope_key)
