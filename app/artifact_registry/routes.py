from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.artifact_registry.presentation import build_inventory, build_overview
from app.artifact_registry.sync_jobs import NoEligibleRegistryTargets, enqueue_all_registry_inventory_sync
from app.platform_operations.notifications.service import record_operational_activity

artifact_registry_bp = Blueprint('artifact_registry', __name__, url_prefix='/artifact-registry')


@artifact_registry_bp.get('/')
@permission_required('artifact_registry.view')
def overview() -> ResponseReturnValue:
    return render_template('artifact_registry/overview.html', overview=build_overview())


@artifact_registry_bp.get('/inventory')
@permission_required('artifact_registry.view')
def inventory() -> ResponseReturnValue:
    context = build_inventory(
        resource=request.args.get('resource', 'projects', type=str),
        search=request.args.get('q', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    template = 'artifact_registry/partials/_inventory_workspace.html' if request.headers.get('HX-Request') == 'true' else 'artifact_registry/inventory.html'
    return render_template(template, inventory=context)


@artifact_registry_bp.post('/sync')
@permission_required('artifact_registry.sync')
def sync_inventory() -> ResponseReturnValue:
    try:
        job, created = enqueue_all_registry_inventory_sync(
            requested_by_user_id=int(current_user.id),
            trigger_type='manual',
        )
    except NoEligibleRegistryTargets as exc:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='artifact_registry_inventory_sync',
            status='warning',
            title='Artifact Registry Sync Blocked',
            message=str(exc),
            detail='Run Full Validation for an enabled Registry provider before retrying.',
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
