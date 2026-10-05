from __future__ import annotations

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.artifact_registry.presentation import (
    build_analytics,
    build_governance,
    build_inventory,
    build_inventory_overview,
    build_inventory_project_detail,
    build_overview,
    build_overview_section,
    build_runtime_usage,
)
from app.artifact_registry.security.presentation import build_security
from app.artifact_registry.sync_jobs import NoEligibleRegistryTargets, enqueue_all_registry_inventory_sync
from app.artifact_registry.webhooks import (
    RegistryWebhookAuthError,
    disable_webhook,
    generate_webhook_token,
    ingest_webhook,
)
from app.dashboards.common.operational import (
    is_htmx_request,
    normalize_dashboard_page_size,
    normalize_operational_tab,
)
from app.extensions import limiter
from app.platform_operations.jobs.dispatcher import JobWorkerUnavailable
from app.platform_operations.notifications.service import record_operational_activity

artifact_registry_bp = Blueprint('artifact_registry', __name__, url_prefix='/artifact-registry')

OVERVIEW_SECTION_TEMPLATES = {
    'kpi_cards': 'artifact_registry/partials/_overview_kpi_cards.html',
    'overview': 'artifact_registry/partials/_overview_operations.html',
    'provider_health': 'artifact_registry/partials/_overview_provider_health.html',
    'capacity': 'artifact_registry/partials/_overview_capacity.html',
    'signals': 'artifact_registry/partials/_overview_signals.html',
    'reporting': 'artifact_registry/partials/_overview_reporting.html',
}


@artifact_registry_bp.get('/')
@permission_required('artifact_registry.view')
def overview() -> ResponseReturnValue:
    context = build_overview(
        provider_id=request.args.get('provider_id', type=int),
        active_tab=normalize_operational_tab(request.args.get('tab', 'overview', type=str)),
        provider_health_page=request.args.get('provider_health_page', 1),
        provider_health_per_page=normalize_dashboard_page_size(request.args.get('provider_health_per_page')),
    )
    template = (
        'artifact_registry/partials/_overview_content.html'
        if is_htmx_request(request.headers)
        else 'artifact_registry/overview.html'
    )
    return render_template(template, overview=context)


@artifact_registry_bp.get('/overview/section/<string:section>')
@permission_required('artifact_registry.view')
def overview_section(section: str) -> ResponseReturnValue:
    template = OVERVIEW_SECTION_TEMPLATES.get(section)
    if template is None:
        abort(404)
    context = build_overview_section(
        section,
        provider_id=request.args.get('provider_id', type=int),
        provider_health_page=request.args.get('provider_health_page', 1),
        provider_health_per_page=normalize_dashboard_page_size(request.args.get('provider_health_per_page')),
    )
    return render_template(template, overview=context)


@artifact_registry_bp.get('/inventory')
@permission_required('artifact_registry.view')
def inventory() -> ResponseReturnValue:
    return render_template(
        'artifact_registry/inventory.html',
        inventory=build_inventory_overview(),
    )


def _inventory_resource_response(resource: str) -> ResponseReturnValue:
    context = build_inventory(
        resource=resource,
        search=request.args.get('q', '', type=str),
        source_id=request.args.get('source_id', type=int),
        environment=request.args.get('environment', '', type=str),
        visibility=request.args.get('visibility', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    template = (
        'artifact_registry/partials/_inventory_workspace.html'
        if request.headers.get('HX-Request') == 'true'
        else 'artifact_registry/inventory_resource.html'
    )
    return render_template(template, inventory=context)


@artifact_registry_bp.get('/inventory/projects')
@permission_required('artifact_registry.view')
def inventory_projects() -> ResponseReturnValue:
    return _inventory_resource_response('projects')


@artifact_registry_bp.get('/inventory/projects/<int:project_id>/details')
@permission_required('artifact_registry.view')
def inventory_project_details(project_id: int) -> ResponseReturnValue:
    project = build_inventory_project_detail(project_id)
    if project is None:
        abort(404)
    return render_template(
        'artifact_registry/partials/_inventory_project_detail.html',
        project=project,
    )


@artifact_registry_bp.get('/inventory/repositories')
@permission_required('artifact_registry.view')
def inventory_repositories() -> ResponseReturnValue:
    return _inventory_resource_response('repositories')


@artifact_registry_bp.get('/inventory/artifacts')
@permission_required('artifact_registry.view')
def inventory_artifacts() -> ResponseReturnValue:
    return _inventory_resource_response('artifacts')


def _security_response(kind: str) -> ResponseReturnValue:
    context = build_security(
        kind=kind,
        search=request.args.get('q', '', type=str),
        severity=request.args.get('severity', '', type=str),
        provider=request.args.get('provider', '', type=str),
        source_id=request.args.get('source_id', type=int),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    template = (
        'artifact_registry/partials/_security_workspace.html'
        if request.headers.get('HX-Request') == 'true'
        else 'artifact_registry/security.html'
    )
    return render_template(template, security=context)


@artifact_registry_bp.get('/security')
@permission_required('artifact_registry.view')
def security() -> ResponseReturnValue:
    return _security_response('vulnerabilities')


@artifact_registry_bp.get('/security/supply-chain')
@permission_required('artifact_registry.view')
def security_supply_chain() -> ResponseReturnValue:
    return _security_response('supply_chain')


@artifact_registry_bp.get('/runtime')
@permission_required('artifact_registry.view')
def runtime() -> ResponseReturnValue:
    return render_template(
        'artifact_registry/runtime.html',
        runtime=build_runtime_usage(
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
        ),
    )


@artifact_registry_bp.get('/analytics')
@permission_required('artifact_registry.view')
def analytics() -> ResponseReturnValue:
    return render_template('artifact_registry/analytics.html', analytics=build_analytics())


@artifact_registry_bp.get('/governance')
@permission_required('artifact_registry.view')
def governance() -> ResponseReturnValue:
    return render_template('artifact_registry/governance.html', governance=build_governance())


@artifact_registry_bp.post('/webhooks/<int:integration_instance_id>/token')
@permission_required('integrations.manage')
def webhook_token(integration_instance_id: int) -> ResponseReturnValue:
    token = generate_webhook_token(integration_instance_id)
    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'artifact_registry/partials/_webhook_token_created.html',
            webhook_token=token,
        )
    return jsonify({'token': token, 'display_once': True})


@artifact_registry_bp.post('/webhooks/<int:integration_instance_id>/disable')
@permission_required('integrations.manage')
def webhook_disable(integration_instance_id: int) -> ResponseReturnValue:
    disable_webhook(integration_instance_id)
    return redirect(url_for('artifact_registry.governance'))


@artifact_registry_bp.post('/webhooks/<int:integration_instance_id>')
@limiter.limit('60 per minute')
def webhook_receive(integration_instance_id: int) -> ResponseReturnValue:
    authorization = str(request.headers.get('Authorization') or '').strip()
    bearer = authorization[7:].strip() if authorization.lower().startswith('bearer ') else ''
    token = bearer or str(request.headers.get('X-KAORI-Webhook-Token') or '').strip()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'accepted': False, 'error': 'invalid_json'}), 400
    try:
        event, created = ingest_webhook(
            integration_instance_id=integration_instance_id,
            token=token,
            payload=payload,
        )
    except RegistryWebhookAuthError:
        return jsonify({'accepted': False, 'error': 'unauthorized'}), 401
    except LookupError:
        return jsonify({'accepted': False, 'error': 'registry_not_found'}), 404
    return jsonify(
        {
            'accepted': True,
            'event_id': event.id,
            'event_type': event.event_type,
            'status': event.status,
            'duplicate': not created,
            'job_execution_id': event.job_execution_id,
        }
    ), 202


@artifact_registry_bp.post('/sync')
@permission_required('artifact_registry.sync')
def sync_inventory() -> ResponseReturnValue:
    try:
        job, created = enqueue_all_registry_inventory_sync(
            requested_by_user_id=int(current_user.id),
            trigger_type='manual',
        )
    except JobWorkerUnavailable as exc:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='artifact_registry_inventory_sync',
            status='warning',
            title='Artifact Registry Worker Unavailable',
            message=str(exc),
            detail=(
                'Restart the inventory worker so it advertises the Registry inventory task, '
                'then retry synchronization.'
            ),
            action_url=url_for('artifact_registry.overview'),
            action_label='Open Artifact Registry',
            action_icon='package',
            queue_feedback=True,
        )
    except NoEligibleRegistryTargets as exc:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='artifact_registry_inventory_sync',
            status='warning',
            title='Artifact Registry Sync Blocked',
            message=str(exc),
            detail='Validate the Registry read contract, then retry inventory synchronization.',
            action_url=url_for('artifact_registry.overview'),
            action_label='Open Artifact Registry',
            action_icon='package',
            queue_feedback=True,
        )
    else:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='artifact_registry_inventory_sync',
            status='success',
            title='Artifact Registry Sync Queued' if created else 'Artifact Registry Sync Already Active',
            message='The inventory worker will collect and atomically commit provider-neutral Registry evidence.',
            detail=f'Job Execution #{job.id} owns progress and completion evidence.',
            action_url=url_for('artifact_registry.overview'),
            action_label='Open Artifact Registry',
            action_icon='package',
            queue_feedback=True,
        )
    return redirect(url_for('artifact_registry.overview'))
