from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.access.rbac.decorators import permission_required
from app.common.http import htmx_target, is_htmx_request
from app.integrations.binding_web import binding_response as _binding_response
from app.integrations.domain_service import (
    BindingRegistryFilters,
    ProviderRegistryFilters,
    build_integration_domain_page,
)
from app.integrations.observability.metrics_source.application.registration_web import (
    new_instance_response,
    test_new_instance_connection_response,
)
from app.integrations.observability.metrics_source.providers import provider_definitions
from app.integrations.orchestration.container_orchestrator.frontpage import (
    KubernetesCoverageFilters,
    KubernetesFrontPageFilters,
    KubernetesRegistryFilters,
    build_kubernetes_page,
    build_kubernetes_registry_row,
)
from app.integrations.orchestration.container_orchestrator.tenant_capsule_web import capsule_rbac_operation
from app.integrations.overview_workspace import build_integrations_overview
from app.integrations.provider_matrix import provider_kinds
from app.integrations.repository import get_kubernetes_connection_by_cluster_id
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.service import (
    MetricsSourceRegistryFilters,
    build_alertmanager_page,
    build_integration_runtime_detail,
    build_kubernetes_capability_registry,
    build_kubernetes_detail,
    build_metrics_source_page,
)
from app.integrations.taxonomy import get_domain_definition
from app.integrations.validation.state import (
    build_validation_snapshot,
    get_active_validation_task_id,
)
from app.integrations.validation.web import (
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
    validation_poll_response,
)
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')


@integrations_bp.get('/')
@permission_required('integrations.manage')
def overview() -> ResponseReturnValue:
    context = build_integrations_overview(
        tab=request.args.get('tab', 'catalog').strip(),
        integration_type=request.args.get('integration_type', '').strip(),
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
    is_workspace_partial = is_htmx_request() and htmx_target() == 'domain-workspace'
    context = build_integration_domain_page(
        domain_key,
        active_tab=request.args.get('tab', 'registry').strip(),
        provider_filters=ProviderRegistryFilters(
            query=request.args.get('provider_q', '').strip(),
            provider_key=request.args.get('provider_key', '').strip(),
            readiness=request.args.get('provider_readiness', '').strip(),
            page=request.args.get('provider_page', 1, type=int) or 1,
            per_page=request.args.get('provider_per_page', 5, type=int) or 5,
        ),
        binding_filters=BindingRegistryFilters(
            query=request.args.get('binding_q', '').strip(),
            provider=request.args.get('binding_provider', '').strip(),
            status=request.args.get('binding_status', '').strip(),
            page=request.args.get('binding_page', 1, type=int) or 1,
            per_page=request.args.get('binding_per_page', 5, type=int) or 5,
        ),
        include_capabilities=not is_workspace_partial,
    )
    if is_workspace_partial:
        return render_template('integrations/partials/_domain_workspace.html', **context)
    return render_template('integrations/domain.html', **context)


@integrations_bp.get('/orchestration')
@permission_required('integrations.manage')
def orchestration() -> ResponseReturnValue:
    return _render_domain_page('orchestration')


@integrations_bp.get('/observability')
@permission_required('integrations.manage')
def observability() -> ResponseReturnValue:
    return _render_domain_page('observability')


@integrations_bp.get('/storage')
@permission_required('integrations.manage')
def storage() -> ResponseReturnValue:
    return _render_domain_page('storage')


@integrations_bp.get('/registry')
@permission_required('integrations.manage')
def registry() -> ResponseReturnValue:
    return _render_domain_page('registry')


@integrations_bp.get('/secrets-management')
@permission_required('integrations.manage')
def secrets_management() -> ResponseReturnValue:
    return _render_domain_page('secrets_management')


@integrations_bp.get('/source-control')
@permission_required('integrations.manage')
def source_control() -> ResponseReturnValue:
    return _render_domain_page('source_control')


# The provider matrix defines which implementations may register; destinations
# remain provider-owned routes, never a second KAORI registration implementation.
_PROVIDER_REGISTRATION_ENDPOINTS = {
    ('container_orchestrator', 'kubernetes'): 'cluster.add_cluster',
    ('alert_source', 'alertmanager'): 'alertmanager.new_instance',
    ('object_storage', 'minio'): 'minio.new_instance',
    ('registry', 'harbor'): 'harbor.new_instance',
    ('secrets_pki', 'vault'): 'vault.new_instance',
    ('source_control', 'github'): 'github_source.new_connection',
}


@integrations_bp.get('/providers/<string:integration_type>')
@permission_required('integrations.manage')
def choose_integration_provider(integration_type: str) -> ResponseReturnValue:
    """Select an admitted provider before entering its owned registration form."""
    if integration_type == 'metrics_source':
        return redirect(url_for('integrations.select_metrics_source_provider'))

    kinds = sorted(provider_kinds(integration_type), key=lambda kind: (not kind.available, kind.label.casefold()))
    if not kinds:
        abort(404)

    domain = get_domain_definition(kinds[0].domain_key)
    providers = [
        {
            'key': kind.key,
            'label': kind.label,
            'adapter': (
                'Not implemented'
                if kind.adapter_key == 'not_implemented'
                else kind.adapter_key.replace('_', ' ').title()
            ),
            'protocol': ('Not defined' if kind.protocol == 'not_defined' else kind.protocol.replace('_', ' ').upper()),
            'lifecycle': kind.lifecycle,
            'available': kind.available,
            'registration_url': (
                url_for(_PROVIDER_REGISTRATION_ENDPOINTS[(kind.integration_type, kind.key)])
                if kind.available and (kind.integration_type, kind.key) in _PROVIDER_REGISTRATION_ENDPOINTS
                else None
            ),
        }
        for kind in kinds
    ]
    return render_template(
        'integrations/provider_selector.html',
        domain=domain,
        integration_type=integration_type,
        providers=providers,
        available_count=sum(bool(provider['registration_url']) for provider in providers),
    )


@integrations_bp.get('/runtime/<string:detail_key>/details')
@permission_required('integrations.manage')
def runtime_overview_details(detail_key: str) -> ResponseReturnValue:
    integration_type, separator, instance_id = detail_key.partition(':')
    if not separator or not integration_type or not instance_id:
        abort(404)
    detail = build_integration_runtime_detail(integration_type, instance_id)
    if detail is None:
        abort(404)
    return render_template(
        'integrations/partials/_runtime_overview_modal.html',
        detail=detail,
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
    flash(
        'Capsule RBAC check: '
        + (
            'all canonical roles match.'
            if result['status'] == 'ready'
            else 'review missing or conflicting role prerequisites in the cluster panel.'
        ),
        'success' if result['status'] == 'ready' else 'warning',
    )
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id, tab='validation'))


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
    flash(
        'Capsule ClusterRole bootstrap '
        + (
            'completed and verified.'
            if result['status'] == 'ready'
            else 'requires operator attention; no conflicting roles were overwritten.'
        ),
        'success' if result['status'] == 'ready' else 'warning',
    )
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id, tab='validation'))


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


@integrations_bp.get('/observability/metrics-sources/new')
@permission_required('integrations.manage')
def select_metrics_source_provider() -> ResponseReturnValue:
    # Keep provider-specific capability definitions authoritative while reusing
    # the same admitted/planned registration contract as other Integrations.
    admitted_kinds = {kind.key: kind for kind in provider_kinds('metrics_source')}
    providers = [
        {
            'key': provider.key,
            'label': provider.label,
            'description': provider.description,
            'icon': provider.icon,
            'adapter_key': provider.adapter_key,
            'query_language': provider.query_language,
            'adapter': provider.adapter_key.replace('_', ' ').title(),
            'protocol': provider.query_language.upper(),
            'secondary_label': 'Query Language',
            'lifecycle': admitted_kinds[provider.key].lifecycle,
            'registration_url': (
                url_for('integrations.register_metrics_source', provider_key=provider.key)
                if admitted_kinds[provider.key].available
                else None
            ),
        }
        for provider in provider_definitions()
    ]
    return render_template(
        'integrations/observability/metrics_source/provider_selector.html',
        domain=get_domain_definition('observability'),
        integration_type='metrics_source',
        providers=providers,
        available_count=sum(bool(provider['registration_url']) for provider in providers),
        guide_title='Metrics Provider Selection',
        guide_text=(
            'Metrics adapters define protocol, query language, validation and query horizon. '
            'KAORI manages connection evidence and qualified consumer routing.'
        ),
    )


@integrations_bp.route('/observability/metrics-sources/<string:provider_key>/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def register_metrics_source(provider_key: str) -> ResponseReturnValue:
    return new_instance_response(provider_key=provider_key)


@integrations_bp.post('/observability/metrics-sources/<string:provider_key>/test-connection')
@permission_required('integrations.manage')
def test_metrics_source(provider_key: str) -> ResponseReturnValue:
    return test_new_instance_connection_response(provider_key=provider_key)


@integrations_bp.get('/observability/metrics-sources')
@permission_required('integrations.manage')
def metrics_sources() -> ResponseReturnValue:
    context = build_metrics_source_page(
        filters=MetricsSourceRegistryFilters(
            query=request.args.get('q', '').strip(),
            provider_key=request.args.get('provider_key', '').strip(),
            compatibility=request.args.get('compatibility', '').strip(),
            readiness=request.args.get('readiness', '').strip(),
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
        ),
        tab=request.args.get('tab', 'coverage').strip(),
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
        if target == 'metrics-source-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        if target == 'metrics-source-inventory-card':
            return render_template(
                'integrations/observability/metrics_source/partials/_instance_inventory.html', **context
            )
        return render_template('integrations/observability/metrics_source/partials/_inventory_content.html', **context)
    return render_template('integrations/observability/metrics_source/frontpage.html', **context)


@integrations_bp.get('/alertmanager')
@permission_required('integrations.manage')
def alertmanager() -> ResponseReturnValue:
    context = build_alertmanager_page(
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
        if target == 'alertmanager-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        if target == 'alertmanager-inventory-card':
            return render_template(
                'integrations/observability/alert_source/providers/alertmanager/partials/_inventory_card.html',
                **context,
            )
        return render_template(
            'integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html', **context
        )
    return render_template('integrations/observability/alert_source/providers/alertmanager/frontpage.html', **context)


@integrations_bp.route('/metrics-sources/bind', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def bind_metrics_source() -> ResponseReturnValue:
    scope_key = request.values.get('scope_key', '').strip()
    if not scope_key:
        abort(400)
    return _binding_response('metrics_source', scope_key=scope_key)


@integrations_bp.route('/alertmanager/bind', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def bind_alertmanager_source() -> ResponseReturnValue:
    scope_key = request.values.get('scope_key', '').strip()
    if not scope_key:
        abort(400)
    return _binding_response('alert_source', scope_key=scope_key)
