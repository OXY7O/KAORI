from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.extensions import db
from app.integrations.coverage import build_binding_workspace
from app.integrations.service import build_alertmanager_page, build_integrations_overview, build_kubernetes_detail, build_kubernetes_page, build_prometheus_page
from app.rbac.decorators import permission_required
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.integrations.validation.web import (
    enqueue_instance_validation,
    snapshot_feedback_for_user,
    validate_snapshot_access,
)
from app.models import AlertmanagerInstance, Cluster, PrometheusInstance
from app.models.integration import KubernetesConnection
from app.notifications.service import get_navigation_notification_context, record_operational_activity

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
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/partials/_runtime_overview.html', **context)
    return render_template('integrations/overview.html', **context)


@integrations_bp.get('/kubernetes')
@permission_required('settings.manage_integrations')
def kubernetes() -> ResponseReturnValue:
    context = build_kubernetes_page(
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/kubernetes/partials/_registry.html', **context)
    return render_template('integrations/kubernetes.html', **context)


@integrations_bp.get('/kubernetes/<string:cluster_id>')
@permission_required('clusters.view')
def kubernetes_detail(cluster_id: str) -> ResponseReturnValue:
    context = build_kubernetes_detail(cluster_id)
    if context is None:
        abort(404)
    connection = context['connection']
    task_id = get_active_validation_task_id(
        provider_type='kubernetes',
        operation='runtime_refresh',
        instance_id=connection.id,
    )
    context['validation_job'] = build_validation_snapshot(task_id) if task_id else None
    return render_template('integrations/kubernetes/detail.html', **context)


@integrations_bp.post('/kubernetes/<string:cluster_id>/runtime/refresh')
@permission_required('clusters.sync')
def kubernetes_runtime_refresh(cluster_id: str) -> ResponseReturnValue:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first_or_404()
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        validation_job, created = enqueue_instance_validation(
            provider_type='kubernetes',
            instance_id=connection.id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_runtime_validation_queued' if created else 'kubernetes_runtime_validation_already_running',
            status='info' if created else 'warning',
            title='Kubernetes runtime validation queued' if created else 'Kubernetes runtime validation already running',
            message=(
                f'KAORI queued runtime and capability validation for {connection.cluster.name}.'
                if created
                else f'Runtime validation is already running for {connection.cluster.name}.'
            ),
            detail=(
                'The dedicated validation worker will refresh API compatibility and capability evidence.'
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
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_runtime_validation_enqueue_failed',
            status='error',
            title='Kubernetes runtime validation not queued',
            message=f'KAORI could not queue runtime validation for {connection.cluster.name}.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime',
            action_label='Review Kubernetes runtime',
            action_icon='activity',
            metadata={'cluster_id': cluster_id, 'connection_id': connection.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        context = build_kubernetes_detail(cluster_id)
        if context is None:
            abort(404)
        context.update({
            'validation_job': validation_job,
            'operation_feedback': feedback,
            'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
        })
        return render_template('integrations/kubernetes/partials/_runtime_workspace.html', **context)
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime')


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/refresh/status/<string:task_id>')
@permission_required('clusters.view')
def kubernetes_runtime_refresh_status(cluster_id: str, task_id: str) -> ResponseReturnValue:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first_or_404()
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        provider_type='kubernetes',
        instance_id=connection.id,
    ):
        abort(404)
    context = build_kubernetes_detail(cluster_id)
    if context is None:
        abort(404)
    context.update({
        'validation_job': snapshot,
        'operation_feedback': snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
        'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
    })
    return render_template('integrations/kubernetes/partials/_runtime_workspace.html', **context)


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/history')
@permission_required('clusters.view')
def kubernetes_runtime_history(cluster_id: str) -> ResponseReturnValue:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first_or_404()
    rows, pagination = paginate_runtime_history(
        'kubernetes',
        str(connection.id),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    return render_template(
        'integrations/kubernetes/partials/_runtime_history.html',
        history=runtime_history_view(rows, pagination=pagination),
        cluster=connection.cluster,
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
        if request.headers.get('HX-Target') == 'prometheus-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
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
        if request.headers.get('HX-Target') == 'alertmanager-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        return render_template('integrations/alertmanager/partials/_inventory_content.html', **context)
    return render_template('integrations/alertmanager.html', **context)



def _is_htmx_request() -> bool:
    return request.headers.get('HX-Request') == 'true'


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
        cluster = Cluster.query.filter_by(id=cluster_id).first()
        source = None
        try:
            if cluster is None:
                raise ValueError('The selected Kubernetes scope no longer exists.')
            if source_id is None:
                raise ValueError(f'Select an existing {provider_type.title()} source.')
            if provider_type == 'prometheus':
                from app.prometheus.service import create_prometheus_binding
                source = PrometheusInstance.query.filter_by(id=source_id).first()
                if source is None:
                    raise ValueError('The selected Prometheus source no longer exists.')
                binding = create_prometheus_binding(
                    instance=source,
                    cluster=cluster,
                    role=role,
                    priority=priority,
                    selector_label=selector_label,
                    selector_value=selector_value,
                    selector_operator=selector_operator,
                )
            else:
                from app.alertmanager.forms import AlertmanagerBindingForm
                from app.alertmanager.service import add_alertmanager_binding
                source = AlertmanagerInstance.query.filter_by(id=source_id).first()
                if source is None:
                    raise ValueError('The selected Alertmanager source no longer exists.')
                binding = add_alertmanager_binding(
                    instance=source,
                    form=AlertmanagerBindingForm(
                        scope_type='kubernetes_cluster',
                        scope_key=cluster.id,
                        binding_role=role,
                        priority=priority,
                        enabled=True,
                        selector_label=selector_label,
                        selector_value=selector_value,
                        selector_operator=selector_operator,
                    ),
                )
        except ValueError as exc:
            db.session.rollback()
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
                queue_feedback=not _is_htmx_request(),
            )
        except Exception as exc:
            db.session.rollback()
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
                queue_feedback=not _is_htmx_request(),
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
                queue_feedback=not _is_htmx_request(),
            )
            if not _is_htmx_request():
                return redirect(
                    url_for(
                        'integrations.prometheus' if provider_type == 'prometheus' else 'integrations.alertmanager'
                    ) + '#integration-coverage'
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
        get_navigation_notification_context(user_id=int(current_user.id))
        if feedback is not None
        else None
    )
    if _is_htmx_request():
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
