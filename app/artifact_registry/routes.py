from __future__ import annotations

import json

from typing import Any

from celery.exceptions import CeleryError
from flask import Blueprint, abort, jsonify, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.artifact_registry.analytics_job_adapter import (
    build_registry_analytics_readiness,
    get_registry_analytics_job,
    should_request_registry_analytics_materialization,
)
from app.artifact_registry.governance_job_adapter import (
    build_registry_governance_sync_state,
    get_registry_governance_sync_job,
)
from app.artifact_registry.presentation import (
    build_analytics,
    build_analytics_shell,
    build_governance,
    build_inventory,
    build_inventory_artifact_detail,
    build_inventory_overview,
    build_inventory_project_detail,
    build_inventory_repository_detail,
    build_overview,
    build_overview_section,
    build_runtime_binding_detail,
    build_runtime_usage,
)
from app.artifact_registry.security.job_adapter import (
    build_registry_security_sync_state,
    get_registry_security_sync_job,
)
from app.artifact_registry.security.presentation import build_security
from app.artifact_registry.sync_jobs import NoEligibleRegistryTargets, enqueue_all_registry_inventory_sync
from app.artifact_registry.webhooks import RegistryWebhookAuthError, ingest_webhook
from app.dashboards.common.operational import (
    is_htmx_request,
    normalize_dashboard_page_size,
    normalize_operational_tab,
)
from app.extensions import limiter
from app.extensions.db import db
from app.platform_operations.jobs.dispatcher import JobWorkerUnavailable, dispatch_registered_job
from app.platform_operations.jobs.service import JobQuotaExceeded
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


@artifact_registry_bp.get('/inventory/repositories/<int:repository_id>/details')
@permission_required('artifact_registry.view')
def inventory_repository_details(repository_id: int) -> ResponseReturnValue:
    repository = build_inventory_repository_detail(repository_id)
    if repository is None:
        abort(404)
    return render_template(
        'artifact_registry/partials/_inventory_repository_detail.html',
        repository=repository,
    )


@artifact_registry_bp.get('/inventory/artifacts')
@permission_required('artifact_registry.view')
def inventory_artifacts() -> ResponseReturnValue:
    return _inventory_resource_response('artifacts')


@artifact_registry_bp.get('/inventory/artifacts/<int:artifact_id>/details')
@permission_required('artifact_registry.view')
def inventory_artifact_details(artifact_id: int) -> ResponseReturnValue:
    artifact = build_inventory_artifact_detail(artifact_id)
    if artifact is None:
        abort(404)
    return render_template(
        'artifact_registry/partials/_inventory_artifact_detail.html',
        artifact=artifact,
    )


def _security_response(kind: str) -> ResponseReturnValue:
    context = build_security(
        kind=kind,
        section=request.args.get('section', '', type=str),
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


def _security_sync_context(kind: str) -> dict[str, object]:
    return build_security(
        kind=kind,
        section=request.form.get('section', '', type=str),
        search=request.form.get('q', '', type=str),
        severity=request.form.get('severity', '', type=str),
        provider=request.form.get('provider', '', type=str),
        source_id=request.form.get('source_id', type=int),
        page=request.form.get('page', 1, type=int) or 1,
        per_page=request.form.get('per_page', 5, type=int) or 5,
    )


@artifact_registry_bp.post('/security/sync')
@permission_required('artifact_registry.sync')
def security_sync() -> ResponseReturnValue:
    is_htmx = request.headers.get('HX-Request') == 'true'
    kind = 'supply_chain' if request.form.get('view') == 'supply_chain' else 'vulnerabilities'
    outcome = None

    try:
        outcome = dispatch_registered_job(
            job_key='artifact_registry.security.sync',
            trigger_type='manual',
            requested_by_user_id=int(current_user.id),
        )
    except JobWorkerUnavailable as exc:
        accepted = False
        status = 'error'
        title = 'Security Sync Worker Unavailable'
        message = str(exc)
        detail = 'Restart the inventory worker so it advertises the Registry security task, then retry.'
        job = None
    else:
        accepted = outcome.accepted
        job = outcome.job
        if accepted:
            status = 'success' if outcome.created else 'info'
            title = 'Security Sync Queued' if outcome.created else 'Security Sync Already Active'
            message = outcome.message
            detail = 'Security Sync is read-only and never triggers provider scans.'
        else:
            status = 'warning'
            title = 'Security Sync Could Not Start'
            message = outcome.message
            detail = 'Committed Registry inventory and an eligible provider security collector are required.'

    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type='artifact_registry_security_sync',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('artifact_registry.security'),
        action_label='Open Registry Security',
        action_icon='shield-check',
        metadata={
            'job_key': 'artifact_registry.security.sync',
            'job_public_id': job.public_id if job is not None else None,
            'created': bool(accepted and outcome is not None and outcome.created),
        },
        queue_feedback=not is_htmx,
    )

    if is_htmx:
        rendered = ''.join(
            (
                render_template(
                    'artifact_registry/partials/_security_workspace.html',
                    security=_security_sync_context(kind),
                ),
                render_template(
                    'components/operational_toast.html',
                    **feedback,
                    toast_oob=True,
                ),
            )
        )
        response = make_response(rendered, 202 if accepted else (409 if status == 'warning' else 503))
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response

    return redirect(
        url_for('artifact_registry.security_supply_chain' if kind == 'supply_chain' else 'artifact_registry.security')
    )


@artifact_registry_bp.get('/security/sync/status/<string:public_id>')
@permission_required('artifact_registry.sync')
def security_sync_status(public_id: str) -> ResponseReturnValue:
    job = get_registry_security_sync_job(public_id)
    if job is None:
        abort(404)

    response = make_response(
        render_template(
            'artifact_registry/partials/_security_sync_live_state.html',
            security_sync_state=build_registry_security_sync_state(),
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    if not job.is_active:
        response.headers['HX-Trigger-After-Swap'] = json.dumps(
            {
                'artifactRegistrySecuritySyncFinished': True,
                'kaori:notifications-changed': True,
            }
        )
    return response


@artifact_registry_bp.get('/runtime')
@permission_required('artifact_registry.view')
def runtime() -> ResponseReturnValue:
    context = build_runtime_usage(
        search=request.args.get('q', '', type=str),
        source_id=request.args.get('source_id', type=int),
        cluster_id=request.args.get('cluster_id', '', type=str),
        namespace=request.args.get('namespace', '', type=str),
        match_type=request.args.get('match_type', '', type=str),
        exposure=request.args.get('exposure', '', type=str),
        artifact_id=request.args.get('artifact_id', type=int),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    template = (
        'artifact_registry/partials/_runtime_workspace.html'
        if request.headers.get('HX-Request') == 'true'
        else 'artifact_registry/runtime.html'
    )
    return render_template(template, runtime=context)


@artifact_registry_bp.get('/runtime/<int:binding_id>/details')
@permission_required('artifact_registry.view')
def runtime_binding_details(binding_id: int) -> ResponseReturnValue:
    binding = build_runtime_binding_detail(binding_id)
    if binding is None:
        abort(404)
    return render_template(
        'artifact_registry/partials/_runtime_binding_detail.html',
        binding=binding,
    )


_REGISTRY_ANALYTICS_DETAIL_ROUTES = {
    'growth': 'artifact_registry.analytics_growth',
    'capacity': 'artifact_registry.analytics_capacity',
    'usage': 'artifact_registry.analytics_usage',
    'risk': 'artifact_registry.analytics_risk',
    'governance': 'artifact_registry.analytics_governance',
    'alerts': 'artifact_registry.analytics_alerts',
    'insights': 'artifact_registry.analytics_insights',
}


def _render_registry_analytics_page(section: str) -> ResponseReturnValue:
    return render_template(
        'artifact_registry/analytics.html',
        analytics=build_analytics_shell(
            active_tab=section,
            provider_id=request.args.get('provider_id', type=int),
            snapshot_window=request.args.get('snapshot_window', 'current', type=str),
            alert_search=request.args.get('alert_q', '', type=str),
            alert_severity=request.args.get('alert_severity', 'all', type=str),
            alert_state=request.args.get('alert_state', 'all', type=str),
            alert_source=request.args.get('alert_source', 'all', type=str),
            alert_page=request.args.get('alert_page', 1, type=int) or 1,
            alert_per_page=request.args.get('alert_per_page', 5, type=int) or 5,
        ),
    )


@artifact_registry_bp.get('/analytics')
@permission_required('artifact_registry.view')
def analytics() -> ResponseReturnValue:
    legacy_tab = request.args.get('tab', '', type=str)
    if legacy_tab in _REGISTRY_ANALYTICS_DETAIL_ROUTES:
        alert_args = {
            key: value
            for key in (
                'provider_id', 'snapshot_window', 'alert_q', 'alert_severity',
                'alert_state', 'alert_source', 'alert_page', 'alert_per_page',
            )
            if (value := request.args.get(key))
        }
        return redirect(url_for(_REGISTRY_ANALYTICS_DETAIL_ROUTES[legacy_tab], **alert_args))
    return _render_registry_analytics_page('overview')


@artifact_registry_bp.get('/analytics/growth')
@permission_required('artifact_registry.view')
def analytics_growth() -> ResponseReturnValue:
    return _render_registry_analytics_page('growth')


@artifact_registry_bp.get('/analytics/capacity')
@permission_required('artifact_registry.view')
def analytics_capacity() -> ResponseReturnValue:
    return _render_registry_analytics_page('capacity')


@artifact_registry_bp.get('/analytics/usage')
@permission_required('artifact_registry.view')
def analytics_usage() -> ResponseReturnValue:
    return _render_registry_analytics_page('usage')


@artifact_registry_bp.get('/analytics/risk')
@permission_required('artifact_registry.view')
def analytics_risk() -> ResponseReturnValue:
    return _render_registry_analytics_page('risk')


@artifact_registry_bp.get('/analytics/governance')
@permission_required('artifact_registry.view')
def analytics_governance() -> ResponseReturnValue:
    return _render_registry_analytics_page('governance')


@artifact_registry_bp.get('/analytics/alerts')
@permission_required('artifact_registry.view')
def analytics_alerts() -> ResponseReturnValue:
    return _render_registry_analytics_page('alerts')


@artifact_registry_bp.get('/analytics/insights')
@permission_required('artifact_registry.view')
def analytics_insights() -> ResponseReturnValue:
    return _render_registry_analytics_page('insights')


@artifact_registry_bp.get('/analytics/materialization/resolve')
@permission_required('artifact_registry.view')
def analytics_materialization_resolve() -> ResponseReturnValue:
    """K8s-style on-demand preparation: only the worker collects provider evidence."""
    section = request.args.get('section', 'overview', type=str)
    if section not in _REGISTRY_ANALYTICS_DETAIL_ROUTES:
        section = 'overview'
    provider_id = request.args.get('provider_id', type=int)
    window = request.args.get('snapshot_window', 'current', type=str)
    analytics = build_analytics_shell(
        active_tab=section, provider_id=provider_id, snapshot_window=window
    )
    # The canonical worker materializes the entire fleet regardless of the viewer's filter.
    if should_request_registry_analytics_materialization(build_registry_analytics_readiness()):
        try:
            result = dispatch_registered_job(
                job_key='artifact_registry.analytics.materialize',
                trigger_type='on_demand',
                requested_by_user_id=None,
            )
        except (
            JobWorkerUnavailable,
            JobQuotaExceeded,
            CeleryError,
            KombuOperationalError,
            LookupError,
            OSError,
            RuntimeError,
            SQLAlchemyError,
            ValueError,
        ) as exc:
            db.session.rollback()
            analytics['data_readiness']['collection_warning'] = (
                'The analytics worker could not be started. Check the registered '
                f'analytics-batch worker and JobExecution diagnostics ({type(exc).__name__}).'
            )
        else:
            if not result.accepted:
                analytics['data_readiness']['collection_warning'] = result.message
            else:
                analytics = build_analytics_shell(
                    active_tab=section, provider_id=provider_id, snapshot_window=window
                )
    response = make_response(
        render_template(
            'artifact_registry/partials/_analytics_controls_readiness.html',
            analytics=analytics,
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@artifact_registry_bp.get('/analytics/collect/status/<string:public_id>')
@permission_required('artifact_registry.view')
def analytics_collect_status(public_id: str) -> ResponseReturnValue:
    job = get_registry_analytics_job(public_id)
    if job is None:
        abort(404)
    response = make_response(
        render_template(
            'artifact_registry/partials/_analytics_collect_live_state.html',
            analytics_readiness=build_registry_analytics_readiness(),
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    if not job.is_active:
        response.headers['HX-Trigger-After-Swap'] = json.dumps(
            {
                'artifactRegistryAnalyticsMaterializationFinished': True,
                'kaori:notifications-changed': True,
            }
        )
    return response


@artifact_registry_bp.get('/analytics/section/<string:section>')
@permission_required('artifact_registry.view')
def analytics_section(section: str) -> ResponseReturnValue:
    allowed = {'summary', 'growth', 'capacity', 'usage', 'risk', 'governance', 'alerts', 'insights'}
    if section not in allowed:
        abort(404)
    context = build_analytics(
        active_tab='growth' if section == 'summary' else section,
        provider_id=request.args.get('provider_id', type=int),
        snapshot_window=request.args.get('snapshot_window', 'current', type=str),
        alert_search=request.args.get('alert_q', '', type=str),
        alert_severity=request.args.get('alert_severity', 'all', type=str),
        alert_state=request.args.get('alert_state', 'all', type=str),
        alert_source=request.args.get('alert_source', 'all', type=str),
        alert_page=request.args.get('alert_page', 1, type=int) or 1,
        alert_per_page=request.args.get('alert_per_page', 5, type=int) or 5,
    )
    template = (
        'artifact_registry/partials/_analytics_summary.html'
        if section == 'summary'
        else 'artifact_registry/partials/_analytics_section.html'
    )
    return render_template(template, analytics=context)


@artifact_registry_bp.get('/analytics/alerts/table')
@permission_required('artifact_registry.view')
def analytics_alerts_table() -> ResponseReturnValue:
    query_args: dict[str, Any] = request.args.to_dict(flat=True)
    query_args.pop('tab', None)
    if not is_htmx_request(request.headers):
        return redirect(url_for('artifact_registry.analytics_alerts', **query_args))

    context = build_analytics(
        active_tab='alerts',
        provider_id=request.args.get('provider_id', type=int),
        snapshot_window=request.args.get('snapshot_window', 'current', type=str),
        alert_search=request.args.get('alert_q', '', type=str),
        alert_severity=request.args.get('alert_severity', 'all', type=str),
        alert_state=request.args.get('alert_state', 'all', type=str),
        alert_source=request.args.get('alert_source', 'all', type=str),
        alert_page=request.args.get('alert_page', 1, type=int) or 1,
        alert_per_page=request.args.get('alert_per_page', 5, type=int) or 5,
    )
    response = make_response(
        render_template(
            'artifact_registry/partials/_analytics_section.html',
            analytics=context,
        )
    )
    response.headers['HX-Push-Url'] = url_for(
        'artifact_registry.analytics_alerts',
        **query_args,
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Vary'] = 'HX-Request'
    return response


@artifact_registry_bp.get('/governance')
@permission_required('artifact_registry.view')
def governance() -> ResponseReturnValue:
    template = (
        'artifact_registry/partials/_governance_workspace.html'
        if is_htmx_request(request.headers)
        else 'artifact_registry/governance.html'
    )
    return render_template(
        template,
        governance=build_governance(
            active_tab=request.args.get('tab', 'policies', type=str),
            page=request.args.get('page', 1, type=int) or 1,
            per_page=normalize_dashboard_page_size(request.args.get('per_page')),
            search=request.args.get('q', '', type=str),
            provider=request.args.get('provider', '', type=str),
            retention=request.args.get('retention', '', type=str),
            immutability=request.args.get('immutability', '', type=str),
            state=request.args.get('state', '', type=str),
        ),
    )


@artifact_registry_bp.post('/governance/sync')
@permission_required('artifact_registry.sync')
def governance_sync() -> ResponseReturnValue:
    is_htmx = is_htmx_request(request.headers)
    try:
        outcome = dispatch_registered_job(
            job_key='artifact_registry.governance.sync',
            trigger_type='manual',
            requested_by_user_id=int(current_user.id),
        )
    except JobWorkerUnavailable as exc:
        accepted = False
        status = 'error'
        title = 'Governance Sync Worker Unavailable'
        message = str(exc)
        detail = 'Restart the inventory worker so it advertises the Registry governance task, then retry.'
        job = None
        created = False
    else:
        accepted = outcome.accepted
        job = outcome.job
        created = bool(accepted and outcome.created)
        if accepted:
            status = 'success' if outcome.created else 'info'
            title = 'Governance Sync Queued' if outcome.created else 'Governance Sync Already Active'
            message = outcome.message
            detail = 'Governance Sync reads provider policy and replication evidence without mutating Registry state.'
        else:
            status = 'warning'
            title = 'Governance Sync Could Not Start'
            message = outcome.message
            detail = 'Committed Registry inventory and an eligible governance collector are required.'

    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type='artifact_registry_governance_sync',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('artifact_registry.governance'),
        action_label='Open Registry Governance',
        action_icon='scale',
        metadata={
            'job_key': 'artifact_registry.governance.sync',
            'job_public_id': job.public_id if job is not None else None,
            'created': created,
            'accepted': accepted,
        },
        queue_feedback=not is_htmx,
    )

    active_tab = request.form.get('tab', 'policies', type=str)
    page = request.form.get('page', 1, type=int) or 1
    per_page = normalize_dashboard_page_size(request.form.get('per_page'))
    search = request.form.get('q', '', type=str)
    provider = request.form.get('provider', '', type=str)
    retention = request.form.get('retention', '', type=str)
    immutability = request.form.get('immutability', '', type=str)
    state = request.form.get('state', '', type=str)
    if is_htmx:
        rendered = ''.join(
            (
                render_template(
                    'artifact_registry/partials/_governance_workspace.html',
                    governance=build_governance(
                        active_tab=active_tab,
                        page=page,
                        per_page=per_page,
                        search=search,
                        provider=provider,
                        retention=retention,
                        immutability=immutability,
                        state=state,
                    ),
                ),
                render_template(
                    'components/operational_toast.html',
                    **feedback,
                    toast_oob=True,
                ),
            )
        )
        response = make_response(rendered, 202 if accepted else (409 if status == 'warning' else 503))
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response

    return redirect(
        url_for(
            'artifact_registry.governance',
            tab=active_tab,
            page=page,
            per_page=per_page,
            q=search or None,
            provider=provider or None,
            retention=retention or None,
            immutability=immutability or None,
            state=state or None,
        )
    )


@artifact_registry_bp.get('/governance/sync/status/<string:public_id>')
@permission_required('artifact_registry.sync')
def governance_sync_status(public_id: str) -> ResponseReturnValue:
    job = get_registry_governance_sync_job(public_id)
    if job is None:
        abort(404)

    response = make_response(
        render_template(
            'artifact_registry/partials/_governance_sync_live_state.html',
            governance_sync_state=build_registry_governance_sync_state(),
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    if not job.is_active:
        response.headers['HX-Trigger-After-Swap'] = json.dumps(
            {
                'artifactRegistryGovernanceSyncFinished': True,
                'kaori:notifications-changed': True,
            }
        )
    return response


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
                'Restart the inventory worker so it advertises the Registry inventory task, then retry synchronization.'
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
