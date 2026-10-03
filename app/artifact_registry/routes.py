from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.artifact_registry.inventory.presentation import (
    RegistryInventoryFilters,
    build_artifacts,
    build_overview,
    build_projects,
    build_repositories,
)
from app.artifact_registry.inventory.sync_jobs import (
    NoEligibleRegistryTargets,
    enqueue_artifact_registry_inventory_sync,
)
from app.platform_operations.notifications.service import record_operational_activity

artifact_registry_bp = Blueprint('artifact_registry', __name__, url_prefix='/artifact-registry')


def _filters() -> RegistryInventoryFilters:
    return RegistryInventoryFilters(
        query=request.args.get('q', '', type=str),
        provider=request.args.get('provider', '', type=str),
        source_id=request.args.get('source_id', type=int),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )


@artifact_registry_bp.get('/')
@permission_required('artifact_registry.view')
def overview() -> ResponseReturnValue:
    return render_template('artifact_registry/overview.html', overview=build_overview())


@artifact_registry_bp.get('/inventory/projects')
@permission_required('artifact_registry.view')
def projects() -> ResponseReturnValue:
    return render_template(
        'artifact_registry/inventory.html',
        inventory=build_projects(_filters()),
        inventory_kind='projects',
        inventory_title='Projects',
        inventory_description='Committed Registry project and namespace inventory across providers.',
    )


@artifact_registry_bp.get('/inventory/repositories')
@permission_required('artifact_registry.view')
def repositories() -> ResponseReturnValue:
    return render_template(
        'artifact_registry/inventory.html',
        inventory=build_repositories(_filters()),
        inventory_kind='repositories',
        inventory_title='Repositories',
        inventory_description='Committed OCI repository inventory across registered Registry providers.',
    )


@artifact_registry_bp.get('/inventory/artifacts')
@permission_required('artifact_registry.view')
def artifacts() -> ResponseReturnValue:
    return render_template(
        'artifact_registry/inventory.html',
        inventory=build_artifacts(_filters()),
        inventory_kind='artifacts',
        inventory_title='Artifacts',
        inventory_description='Digest-oriented committed OCI artifact inventory and observed tags.',
    )


@artifact_registry_bp.post('/inventory/sync')
@permission_required('artifact_registry.sync')
def sync_inventory() -> ResponseReturnValue:
    try:
        job, created = enqueue_artifact_registry_inventory_sync(
            requested_by_user_id=int(current_user.id),
            trigger_type='manual',
        )
    except NoEligibleRegistryTargets as exc:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='artifact_registry_inventory_sync_blocked',
            status='warning',
            title='Artifact Registry Sync Blocked',
            message=str(exc),
            detail='Register and validate a Registry provider, then retry inventory synchronization.',
            action_url=url_for('integrations.registry'),
            action_label='Open Registry Integrations',
            action_icon='package',
            queue_feedback=True,
        )
    else:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='artifact_registry_inventory_sync',
            status='success' if created else 'info',
            title='Artifact Registry Sync Queued' if created else 'Artifact Registry Sync Already Active',
            message='KAORI will collect provider evidence and atomically update committed Registry inventory.',
            detail=f'Canonical Job Execution #{job.id} owns this inventory synchronization.',
            action_url=url_for('artifact_registry.overview'),
            action_label='Open Artifact Registry',
            action_icon='package-search',
            queue_feedback=True,
        )
    return redirect(request.referrer or url_for('artifact_registry.overview'))
