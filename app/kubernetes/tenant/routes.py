from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any, cast

from flask import Blueprint, abort, current_app, g, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from kubernetes.client.rest import ApiException
from wtforms.validators import ValidationError

from app.access.rbac.decorators import any_permission_required, permission_required
from app.common.pagination import paginate_sequence
from app.kubernetes.tenant.access_service import (
    TenantAccessStateConflictError,
    TenantGroupReconciliationError,
    add_group_membership_by_id_committed,
    add_user_membership_by_id_committed,
    create_access_grant_by_id_committed,
    create_tenant_group_by_id_committed,
    get_tenant_access_context,
    inspect_access_grant_by_id_committed,
    reactivate_membership_by_id_committed,
    reactivate_tenant_group_by_id_committed,
    reconcile_access_grant_by_id_committed,
    retire_tenant_group_by_id_committed,
    revoke_access_grant_by_id_committed,
    revoke_membership_by_id_committed,
    update_tenant_group_by_id_committed,
)
from app.kubernetes.tenant.admin_workspace import (
    get_access_grant_registry_context,
    get_credential_registry_context,
    get_group_registry_context,
    get_membership_registry_context,
    get_namespace_access_registry_context,
    get_tenant_summary_context,
)
from app.kubernetes.tenant.allocation_drift import (
    accept_provider_allocation_state_committed,
    build_allocation_drift_action_state,
    reapply_kaori_allocation_intent_committed,
)
from app.kubernetes.tenant.audit import record_tenant_sync_dispatch_audit
from app.kubernetes.tenant.capacity_governance import (
    TenantCapacityStateConflictError,
    upsert_capacity_policy_committed,
)
from app.kubernetes.tenant.capsule_allocation_governance import (
    CapsuleSharedAllocationStateConflictError,
    accept_capsule_shared_provider_state_committed,
    cutover_capsule_global_quota_allocation_committed,
    get_capsule_shared_allocation_context,
    reapply_capsule_shared_allocation_intent_committed,
)
from app.kubernetes.tenant.capsule_tenant_quota_governance import (
    CapsuleTenantQuotaStateConflictError,
    accept_capsule_tenant_provider_state_committed,
    change_capsule_tenant_resource_quota_committed,
    cutover_capsule_tenant_resource_quota_committed,
    get_capsule_tenant_quota_context,
    reapply_capsule_tenant_quota_intent_committed,
)
from app.kubernetes.tenant.credential_service import (
    GeneratedKubeconfigMaterial,
    GeneratedTokenMaterial,
    HumanCredentialIssueRequest,
    TenantCredentialStateConflictError,
    create_human_credential_from_grant_committed,
    generate_credential_material_committed,
    renew_credential_committed,
    resume_credential_committed,
    revoke_credential_committed,
    suspend_credential_committed,
)
from app.kubernetes.tenant.decommission_service import (
    TenantDecommissionBlocked,
    request_tenant_decommission_committed,
)
from app.kubernetes.tenant.deployer_credential_service import (
    DeployerCredentialIssueRequest,
    create_deployer_credential_committed,
)
from app.kubernetes.tenant.discovery_service import (
    adopt_discovered_tenant_committed,
    get_tenant_adoption_preflight_context,
    get_tenant_discovery_context,
)
from app.kubernetes.tenant.job_adapter import (
    build_tenant_sync_state,
    dispatch_tenant_decommission,
    get_visible_tenant_sync_job,
)
from app.kubernetes.tenant.live_connection import get_live_tenant_connection_context
from app.kubernetes.tenant.overview import dispatch_tenant_inventory_sync
from app.kubernetes.tenant.service import (
    TenantStateConflictError,
    change_native_namespace_allocation_committed,
    create_resource_profile_committed,
    create_tenant_committed,
    cutover_adopted_namespace_allocation_committed,
    delete_resource_profile_committed,
    get_capacity_decision_registry_context,
    get_namespace_registry_context,
    get_resource_profile_registry_context,
    get_tenant_context,
    get_tenant_registry_context,
    provision_native_namespace_committed,
    reconcile_managed_native_namespace_committed,
    rollout_resource_profile_to_tenant_committed,
    update_resource_profile_committed,
)
from app.kubernetes.tenant.workspace import (
    get_tenant_cluster_estate_context,
    get_tenant_operations_evidence_context,
    get_tenant_overview_context,
    get_tenant_sync_workspace_context,
    get_tenant_workspace_context,
)
from app.models import User
from app.models.tenant import TenantCredential
from app.platform_operations.notifications.service import queue_transient_feedback, record_operational_activity

tenant_bp = Blueprint('tenant', __name__, url_prefix='/kubernetes/tenant')


def _csrf() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc


def _record(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    metadata: dict[str, Any],
    detail: str | None = None,
    queue_feedback: bool | None = None,
) -> dict[str, Any]:
    is_htmx = request.headers.get('HX-Request') == 'true'
    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('tenant.index'),
        action_label='Open Tenant',
        action_icon='building-2',
        metadata={**metadata, 'operation_domain': 'kubernetes_tenant', 'feedback_delivery': 'toast'},
        queue_feedback=(not is_htmx) if queue_feedback is None else queue_feedback,
    )
    g.tenant_operational_feedback = feedback
    return feedback


def _tenant_workspace_context() -> dict[str, Any]:
    return {
        **get_tenant_context(),
        **get_tenant_access_context(),
        **get_tenant_workspace_context(),
        **get_tenant_sync_workspace_context(),
    }


_TENANT_ADMIN_SECTIONS = {
    'registry',
    'discovery',
    'tenant-setup',
    'memberships',
    'access-grants',
    'credentials',
    'namespace-access',
}


def _tenant_admin_section(value: str | None) -> str:
    normalized = str(value or 'registry').strip().lower()
    return normalized if normalized in _TENANT_ADMIN_SECTIONS else 'registry'


def _tenant_section_redirect(section: str):
    resolved_section = _tenant_admin_section(section)
    if request.headers.get('HX-Request') != 'true':
        return redirect(url_for('tenant.tenants', section=resolved_section))

    context = _tenant_workspace_context()
    context.update(get_tenant_summary_context())
    context.update(_tenant_active_section_context(resolved_section))
    rendered = render_template(
        'kubernetes/tenant/partials/_tenant_admin_workspace.html',
        active_tenant_section=resolved_section,
        can_manage=current_user.has_permission('tenant.manage'),
        **context,
    )
    feedback = getattr(g, 'tenant_operational_feedback', None)
    if feedback:
        rendered += render_template(
            'components/operational_toast.html',
            **feedback,
            toast_oob=True,
        )
    response = make_response(rendered)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@tenant_bp.get('/')
@any_permission_required('tenant.view', 'tenant.manage')
def index():
    context = _tenant_workspace_context()
    context.update(
        get_tenant_overview_context(
            cluster_page=request.args.get('cluster_page', 1, type=int) or 1,
            cluster_per_page=request.args.get('cluster_per_page', 5, type=int) or 5,
        )
    )
    return render_template(
        'kubernetes/tenant/overview.html',
        tenant_page='overview',
        tenant_page_title='Overview',
        tenant_page_icon='layout-dashboard',
        **context,
    )


@tenant_bp.get('/live-provider-connectivity')
@any_permission_required('tenant.view', 'tenant.manage')
def live_provider_connectivity():
    response = make_response(
        render_template(
            'kubernetes/tenant/partials/_live_connection_snapshot.html',
            **get_live_tenant_connection_context(),
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@tenant_bp.get('/overview/cluster-estate')
@any_permission_required('tenant.view', 'tenant.manage')
def cluster_estate():
    return render_template(
        'kubernetes/tenant/partials/_cluster_estate.html',
        **get_tenant_cluster_estate_context(
            page=request.args.get('cluster_page', 1, type=int) or 1,
            per_page=request.args.get('cluster_per_page', 5, type=int) or 5,
        ),
    )


@tenant_bp.get('/inventory-sync/workspace')
@any_permission_required('tenant.view', 'tenant.manage')
def inventory_sync_workspace():
    response = make_response(
        render_template(
            'kubernetes/tenant/partials/_sync_workspace.html',
            **get_tenant_sync_workspace_context(),
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@tenant_bp.post('/inventory-sync')
@permission_required('tenant.manage')
def inventory_sync():
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        _csrf()
    except ValueError as exc:
        feedback = {
            'accepted': False,
            'event_type': 'kubernetes_tenant_inventory_sync_blocked',
            'status': 'warning',
            'title': 'Tenant Sync Could Not Start',
            'message': str(exc),
            'metadata': {'operation': 'tenant_inventory_sync', 'job_key': 'kubernetes.tenant.sync'},
        }
    else:
        feedback = dispatch_tenant_inventory_sync(requested_by_user_id=int(current_user.id))

    if not feedback.get('accepted'):
        record_tenant_sync_dispatch_audit(
            actor_user_id=int(current_user.id),
            action_status='blocked' if feedback.get('status') == 'warning' else 'failed',
            summary=str(feedback.get('message') or 'Tenant synchronization could not start.'),
            metadata=dict(feedback.get('metadata') or {}),
        )
        recorded_feedback = _record(
            event_type=str(feedback['event_type']),
            status=str(feedback['status']),
            title=str(feedback['title']),
            message=str(feedback['message']),
            detail=str(feedback.get('detail') or '') or None,
            metadata=dict(feedback.get('metadata') or {}),
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            rendered = ''.join(
                (
                    render_template(
                        'kubernetes/tenant/partials/_sync_workspace.html',
                        **get_tenant_sync_workspace_context(),
                    ),
                    render_template(
                        'components/operational_toast.html',
                        **recorded_feedback,
                        toast_oob=True,
                    ),
                )
            )
            response = make_response(rendered)
            response.status_code = 409 if feedback.get('status') == 'warning' else 503
            response.headers['Cache-Control'] = 'no-store, max-age=0'
            return response
        return redirect(url_for('tenant.index'))

    job = feedback['job']
    record_tenant_sync_dispatch_audit(
        actor_user_id=int(current_user.id),
        action_status='queued' if feedback.get('created') else 'already_active',
        summary=(
            'Tenant synchronization was queued for the inventory worker.'
            if feedback.get('created')
            else 'Tenant synchronization was already active when another request was received.'
        ),
        job=job,
        metadata={'created': bool(feedback.get('created')), 'trigger_type': 'manual'},
    )

    if is_htmx:
        response = make_response(
            render_template(
                'kubernetes/tenant/partials/_sync_workspace.html',
                **get_tenant_sync_workspace_context(),
            )
        )
        response.status_code = 202
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response

    queue_transient_feedback(
        status='success' if feedback.get('created') else 'info',
        title='Tenant Sync Queued' if feedback.get('created') else 'Tenant Sync Already Active',
        message=(
            'The inventory worker is refreshing the committed Tenant collection snapshot.'
            if feedback.get('created')
            else 'The existing Tenant sync job remains active.'
        ),
        action_url=url_for('jobs.executions', queue='inventory', search=job.public_id),
        action_label='View Job Progress',
        action_icon='activity',
    )
    return redirect(url_for('tenant.index'))


@tenant_bp.get('/inventory-sync/status/<string:public_id>')
@permission_required('tenant.manage')
def inventory_sync_status(public_id: str):
    job = get_visible_tenant_sync_job(
        public_id=public_id,
        user_id=int(current_user.id),
    )
    if job is None:
        abort(404)

    state = build_tenant_sync_state()
    response = make_response(
        render_template(
            'kubernetes/tenant/partials/_sync_live_state.html',
            tenant_sync_state=state,
            requested_job_public_id=public_id,
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    if not job.is_active:
        response.headers['HX-Trigger-After-Swap'] = json.dumps(
            {
                'tenantInventorySyncFinished': True,
                'kaori:notifications-changed': True,
            }
        )
    return response


def _tenant_active_section_context(section: str) -> dict[str, Any]:
    if section == 'registry':
        return {
            **get_tenant_registry_context(
                page=request.args.get('page', 1, type=int) or 1,
                per_page=request.args.get('per_page', 5, type=int) or 5,
                search=str(request.args.get('search') or ''),
                cluster_id=str(request.args.get('cluster_id') or ''),
                environment=str(request.args.get('environment') or ''),
                lifecycle_status=str(request.args.get('lifecycle_status') or ''),
            ),
        }
    if section == 'discovery':
        return {
            **get_tenant_discovery_context(
                page=request.args.get('discovery_page', 1, type=int) or 1,
                per_page=request.args.get('discovery_per_page', 5, type=int) or 5,
                cluster_id=str(request.args.get('discovery_cluster_id') or ''),
                provider=str(request.args.get('discovery_provider') or ''),
                management=str(request.args.get('discovery_management') or ''),
                search=str(request.args.get('discovery_search') or ''),
            ),
        }
    if section == 'memberships':
        return {
            **get_membership_registry_context(
                page=request.args.get('membership_page', 1, type=int) or 1,
                per_page=request.args.get('membership_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('membership_tenant_id') or ''),
                principal_type=str(request.args.get('membership_principal_type') or ''),
                status=str(request.args.get('membership_status') or ''),
                search=str(request.args.get('membership_search') or ''),
            ),
            **get_group_registry_context(
                page=request.args.get('group_page', 1, type=int) or 1,
                per_page=request.args.get('group_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('group_tenant_id') or ''),
                enabled=str(request.args.get('group_enabled') or ''),
                search=str(request.args.get('group_search') or ''),
            ),
        }
    if section == 'access-grants':
        return {
            **get_access_grant_registry_context(
                page=request.args.get('grant_page', 1, type=int) or 1,
                per_page=request.args.get('grant_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('grant_tenant_id') or ''),
                status=str(request.args.get('grant_status') or ''),
                reconciliation_status=str(request.args.get('grant_reconciliation_status') or ''),
                scope_type=str(request.args.get('grant_scope_type') or ''),
                search=str(request.args.get('grant_search') or ''),
            ),
        }
    if section == 'credentials':
        return {
            **get_credential_registry_context(
                page=request.args.get('credential_page', 1, type=int) or 1,
                per_page=request.args.get('credential_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('credential_tenant_id') or ''),
                credential_type=str(request.args.get('credential_type') or ''),
                status=str(request.args.get('credential_status') or ''),
                search=str(request.args.get('credential_search') or ''),
            ),
        }
    if section == 'namespace-access':
        return get_namespace_access_registry_context(
            page=request.args.get('namespace_access_page', 1, type=int) or 1,
            per_page=request.args.get('namespace_access_per_page', 5, type=int) or 5,
            tenant_id=str(request.args.get('namespace_access_tenant_id') or ''),
            environment=str(request.args.get('namespace_access_environment') or ''),
            credential_status=str(request.args.get('namespace_access_status') or ''),
            search=str(request.args.get('namespace_access_search') or ''),
        )
    return {}


@tenant_bp.get('/tenants')
@any_permission_required('tenant.view', 'tenant.manage')
def tenants():
    active_section = _tenant_admin_section(request.args.get('section'))
    context = _tenant_workspace_context()
    context.update(get_tenant_summary_context())
    context.update(_tenant_active_section_context(active_section))
    return render_template(
        'kubernetes/tenant/tenants.html',
        tenant_page='tenants',
        tenant_page_title='Tenants',
        tenant_page_icon='users-round',
        active_tenant_section=active_section,
        **context,
    )


@tenant_bp.get('/resource-profiles')
@any_permission_required('tenant.view', 'tenant.manage')
def resource_profiles():
    active_view = str(request.args.get('view') or 'profiles').strip().lower()
    if active_view not in {'profiles', 'capacity', 'workflow'}:
        active_view = 'profiles'

    context = _tenant_workspace_context()
    context.update(
        get_resource_profile_registry_context(
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
            search=str(request.args.get('profile_search') or ''),
            profile_class=str(request.args.get('profile_class') or ''),
            state=str(request.args.get('profile_state') or ''),
        )
    )

    capacity_search = str(request.args.get('capacity_search') or '').strip()
    capacity_rows = list(context.get('capacity_governance') or [])
    if capacity_search:
        needle = capacity_search.lower()
        capacity_rows = [
            item
            for item in capacity_rows
            if needle in str(item['cluster'].name).lower() or needle in str(item['cluster'].environment).lower()
        ]
    capacity_items, capacity_pagination = paginate_sequence(
        capacity_rows,
        page=request.args.get('capacity_page', 1, type=int) or 1,
        per_page=request.args.get('capacity_per_page', 5, type=int) or 5,
    )
    context['capacity_governance'] = capacity_items
    context['capacity_pagination'] = capacity_pagination
    context['capacity_filters'] = {'search': capacity_search}

    return render_template(
        'kubernetes/tenant/resource_profiles.html',
        tenant_page='resource_profiles',
        tenant_page_title='Resource Profiles',
        tenant_page_icon='layers-3',
        active_resource_profile_view=active_view,
        **context,
    )


@tenant_bp.get('/namespace-provisioning')
@any_permission_required('tenant.view', 'tenant.manage')
def namespace_provisioning():
    active_view = str(request.args.get('view') or 'provision')
    if active_view not in {'provision', 'allocation', 'decisions'}:
        active_view = 'provision'

    context = _tenant_workspace_context()
    context.update(get_capsule_shared_allocation_context())
    context.update(get_capsule_tenant_quota_context())
    context.update(
        get_namespace_registry_context(
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
            search=str(request.args.get('namespace_search') or ''),
            tenant_id=str(request.args.get('namespace_tenant_id') or ''),
            environment=str(request.args.get('namespace_environment') or ''),
            status=str(request.args.get('namespace_status') or ''),
        )
    )
    if active_view == 'decisions':
        context.update(
            get_capacity_decision_registry_context(
                page=request.args.get('decision_page', 1, type=int) or 1,
                per_page=request.args.get('decision_per_page', 5, type=int) or 5,
                search=str(request.args.get('decision_search') or ''),
                decision=str(request.args.get('decision_result') or ''),
            )
        )
    return render_template(
        'kubernetes/tenant/namespace_provisioning.html',
        tenant_page='namespace_provisioning',
        tenant_page_title='Namespace Provisioning',
        tenant_page_icon='boxes',
        active_namespace_view=active_view,
        **context,
    )


@tenant_bp.get('/operations')
@any_permission_required('tenant.view', 'tenant.manage')
def operations():
    active_tab = str(request.args.get('tab') or 'provisioning')
    if active_tab not in {'provisioning', 'runs-evidence', 'drift-reconcile', 'activity'}:
        active_tab = 'provisioning'

    context = _tenant_workspace_context()

    if active_tab == 'provisioning':
        namespace_context = get_namespace_registry_context(
            page=request.args.get('ops_namespace_page', 1, type=int) or 1,
            per_page=request.args.get('ops_namespace_per_page', 5, type=int) or 5,
            search=str(request.args.get('ops_namespace_search') or ''),
            tenant_id=str(request.args.get('ops_namespace_tenant_id') or ''),
            environment=str(request.args.get('ops_namespace_environment') or ''),
            status=str(request.args.get('ops_namespace_status') or ''),
        )
        context.update(
            {
                'operations_namespace_rows': namespace_context['namespaces'],
                'operations_namespace_pagination': namespace_context['namespace_pagination'],
                'operations_namespace_filters': namespace_context['namespace_registry_filters'],
                'operations_namespace_tenant_options': namespace_context['namespace_registry_tenant_options'],
                'operations_namespace_environment_options': namespace_context['namespace_environment_filter_options'],
                'operations_namespace_status_options': namespace_context['namespace_status_filter_options'],
            }
        )
    elif active_tab == 'runs-evidence':
        context.update(
            get_tenant_operations_evidence_context(
                page=request.args.get('ops_evidence_page', 1, type=int) or 1,
                per_page=request.args.get('ops_evidence_per_page', 5, type=int) or 5,
                evidence_type=str(request.args.get('ops_evidence_type') or 'audit'),
                tenant_id=str(request.args.get('ops_evidence_tenant_id') or ''),
                search=str(request.args.get('ops_evidence_search') or ''),
            )
        )
    elif active_tab == 'drift-reconcile':
        drift_context = get_namespace_registry_context(
            page=request.args.get('ops_drift_page', 1, type=int) or 1,
            per_page=request.args.get('ops_drift_per_page', 5, type=int) or 5,
            search=str(request.args.get('ops_drift_search') or ''),
            tenant_id=str(request.args.get('ops_drift_tenant_id') or ''),
            environment=str(request.args.get('ops_drift_environment') or ''),
            status='drifted',
        )
        provider_context = get_tenant_registry_context(
            page=request.args.get('ops_provider_page', 1, type=int) or 1,
            per_page=request.args.get('ops_provider_per_page', 5, type=int) or 5,
            search=str(request.args.get('ops_provider_search') or ''),
            cluster_id=str(request.args.get('ops_provider_cluster_id') or ''),
            environment=str(request.args.get('ops_provider_environment') or ''),
            lifecycle_status=str(request.args.get('ops_provider_lifecycle') or ''),
        )
        access_context = get_access_grant_registry_context(
            page=request.args.get('ops_access_page', 1, type=int) or 1,
            per_page=request.args.get('ops_access_per_page', 5, type=int) or 5,
            tenant_id=str(request.args.get('ops_access_tenant_id') or ''),
            status=str(request.args.get('ops_access_status') or ''),
            reconciliation_status=str(request.args.get('ops_access_reconciliation') or ''),
            scope_type=str(request.args.get('ops_access_scope') or ''),
            search=str(request.args.get('ops_access_search') or ''),
        )
        context.update(
            get_capsule_shared_allocation_context(
                drift_page=request.args.get('ops_capsule_shared_page', 1, type=int) or 1,
                drift_per_page=request.args.get('ops_capsule_shared_per_page', 5, type=int) or 5,
            )
        )
        context.update(
            get_capsule_tenant_quota_context(
                drift_page=request.args.get('ops_capsule_tenant_quota_page', 1, type=int) or 1,
                drift_per_page=request.args.get('ops_capsule_tenant_quota_per_page', 5, type=int) or 5,
            )
        )
        context.update(
            {
                'operations_drift_rows': drift_context['namespaces'],
                'operations_allocation_drift_state': {
                    str(item.id): build_allocation_drift_action_state(item) for item in drift_context['namespaces']
                },
                'operations_drift_pagination': drift_context['namespace_pagination'],
                'operations_drift_filters': drift_context['namespace_registry_filters'],
                'operations_drift_tenant_options': drift_context['namespace_registry_tenant_options'],
                'operations_drift_environment_options': drift_context['namespace_environment_filter_options'],
                'operations_provider_rows': provider_context['tenant_rows'],
                'operations_provider_pagination': provider_context['tenant_pagination'],
                'operations_provider_filters': provider_context['tenant_registry_filters'],
                'operations_provider_cluster_options': provider_context['tenant_cluster_options'],
                'operations_provider_environment_options': provider_context['tenant_environment_filter_options'],
                'operations_provider_lifecycle_options': provider_context['tenant_lifecycle_filter_options'],
                'operations_access_rows': access_context['access_grant_rows'],
                'operations_access_pagination': access_context['access_grant_pagination'],
                'operations_access_filters': access_context['access_grant_filters'],
                'operations_access_tenant_options': access_context['access_grant_tenant_options'],
                'operations_access_status_options': access_context['access_grant_status_options'],
                'operations_access_reconciliation_options': access_context['access_grant_reconciliation_options'],
                'operations_access_scope_options': access_context['access_grant_scope_options'],
            }
        )

    return render_template(
        'kubernetes/tenant/operations.html',
        tenant_page='operations',
        tenant_page_title='Operations',
        tenant_page_icon='activity',
        active_tab=active_tab,
        can_manage=current_user.has_permission('tenant.manage'),
        **context,
    )


def _required_int(name: str) -> int:
    value = str(request.form.get(name) or '').strip()
    if not value:
        raise ValueError(f'Select {name.replace("_", " ")}.')
    return int(value)


def _optional_int(name: str) -> int | None:
    value = str(request.form.get(name) or '').strip()
    return int(value) if value else None


@tenant_bp.post('/groups')
@permission_required('tenant.manage')
def create_group_route():
    try:
        _csrf()
        group = create_tenant_group_by_id_committed(
            tenant_id=str(request.form.get('tenant_id') or '').strip(),
            name=str(request.form.get('name') or ''),
            subject_name=str(request.form.get('subject_name') or '') or None,
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_group_create_failed',
            status='error',
            title='Tenant Group Creation Failed',
            message=str(exc),
            metadata={'operation': 'create_tenant_group'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_group_created',
            status='success',
            title='Tenant Group Created',
            message=f'{group.name} is available as a Tenant membership principal.',
            metadata={'tenant_id': group.tenant_id, 'group_id': group.public_id, 'operation': 'create_tenant_group'},
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/groups/<int:group_id>/edit')
@permission_required('tenant.manage')
def edit_tenant_group_route(group_id: int):
    try:
        _csrf()
        group = update_tenant_group_by_id_committed(
            group_id=group_id,
            name=str(request.form.get('name') or ''),
            subject_name=str(request.form.get('subject_name') or ''),
            actor_user_id=int(current_user.id),
        )
    except TenantGroupReconciliationError as exc:
        _record(
            event_type='kubernetes_tenant_group_update_reconcile_attention',
            status='warning',
            title='Tenant Group Updated with Reconciliation Attention',
            message=str(exc),
            metadata={'group_id': group_id, 'operation': 'update_tenant_group'},
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_group_update_failed',
            status='error',
            title='Tenant Group Update Failed',
            message=str(exc),
            metadata={'group_id': group_id, 'operation': 'update_tenant_group'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_group_updated',
            status='success',
            title='Tenant Group Updated',
            message=f'{group.name} now binds Kubernetes subject {group.subject_name}.',
            metadata={'tenant_id': group.tenant_id, 'group_id': group.public_id, 'operation': 'update_tenant_group'},
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/groups/<int:group_id>/retire')
@permission_required('tenant.manage')
def retire_tenant_group_route(group_id: int):
    try:
        _csrf()
        group = retire_tenant_group_by_id_committed(
            group_id=group_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_group_retire_failed',
            status='error',
            title='Tenant Group Retire Failed',
            message=str(exc),
            metadata={'group_id': group_id, 'operation': 'retire_tenant_group'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_group_retired',
            status='success',
            title='Tenant Group Retired',
            message=f'{group.name} is retired. Historical membership and grant evidence remain retained.',
            metadata={'tenant_id': group.tenant_id, 'group_id': group.public_id, 'operation': 'retire_tenant_group'},
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/groups/<int:group_id>/reactivate')
@permission_required('tenant.manage')
def reactivate_tenant_group_route(group_id: int):
    try:
        _csrf()
        group = reactivate_tenant_group_by_id_committed(
            group_id=group_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_group_reactivate_failed',
            status='error',
            title='Tenant Group Reactivation Failed',
            message=str(exc),
            metadata={'group_id': group_id, 'operation': 'reactivate_tenant_group'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_group_reactivated',
            status='success',
            title='Tenant Group Reactivated',
            message=f'{group.name} is enabled for future Tenant Membership use.',
            metadata={
                'tenant_id': group.tenant_id,
                'group_id': group.public_id,
                'operation': 'reactivate_tenant_group',
            },
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/memberships/users')
@permission_required('tenant.manage')
def add_user_membership_route():
    try:
        _csrf()
        membership = add_user_membership_by_id_committed(
            tenant_id=str(request.form.get('tenant_id') or '').strip(),
            user_id=_required_int('user_id'),
            subject_name=str(request.form.get('subject_name') or '') or None,
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_membership_create_failed',
            status='error',
            title='Tenant Membership Creation Failed',
            message=str(exc),
            metadata={'operation': 'add_user_membership'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_membership_created',
            status='success',
            title='Tenant User Added',
            message=f'{membership.subject_name} is an active member of {membership.tenant.name}.',
            metadata={
                'tenant_id': membership.tenant_id,
                'membership_id': membership.id,
                'operation': 'add_user_membership',
            },
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/memberships/groups')
@permission_required('tenant.manage')
def add_group_membership_route():
    try:
        _csrf()
        membership = add_group_membership_by_id_committed(
            tenant_id=str(request.form.get('tenant_id') or '').strip(),
            group_id=_required_int('group_id'),
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_membership_create_failed',
            status='error',
            title='Tenant Membership Creation Failed',
            message=str(exc),
            metadata={'operation': 'add_group_membership'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_membership_created',
            status='success',
            title='Tenant Group Added',
            message=f'{membership.subject_name} is an active member of {membership.tenant.name}.',
            metadata={
                'tenant_id': membership.tenant_id,
                'membership_id': membership.id,
                'operation': 'add_group_membership',
            },
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/memberships/<int:membership_id>/reactivate')
@permission_required('tenant.manage')
def reactivate_membership_route(membership_id: int):
    try:
        _csrf()
        membership = reactivate_membership_by_id_committed(
            membership_id=membership_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_membership_reactivate_failed',
            status='error',
            title='Tenant Membership Reactivation Failed',
            message=str(exc),
            metadata={'membership_id': membership_id, 'operation': 'reactivate_membership'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_membership_reactivated',
            status='success',
            title='Tenant Membership Reactivated',
            message=f'{membership.subject_name} is active again. Previous Access Grants remain revoked.',
            detail='Apply a new Access Grant when access should be restored.',
            metadata={
                'membership_id': membership.id,
                'tenant_id': membership.tenant_id,
                'operation': 'reactivate_membership',
            },
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/memberships/<int:membership_id>/revoke')
@permission_required('tenant.manage')
def revoke_membership_route(membership_id: int):
    try:
        _csrf()
        membership = revoke_membership_by_id_committed(
            membership_id=membership_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_membership_revoke_failed',
            status='error',
            title='Tenant Membership Revoke Requires Attention',
            message=str(exc),
            metadata={'membership_id': membership_id, 'operation': 'revoke_membership'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_membership_revoked',
            status='success',
            title='Tenant Membership Revoked',
            message=f'{membership.subject_name} no longer has active Tenant membership.',
            metadata={
                'membership_id': membership.id,
                'tenant_id': membership.tenant_id,
                'operation': 'revoke_membership',
            },
        )
    return _tenant_section_redirect('memberships')


@tenant_bp.post('/access-grants')
@permission_required('tenant.manage')
def create_access_grant_route():
    try:
        _csrf()
        grant = create_access_grant_by_id_committed(
            membership_id=_required_int('membership_id'),
            access_profile=str(request.form.get('access_profile') or ''),
            scope_type=str(request.form.get('scope_type') or ''),
            tenant_environment_id=_optional_int('tenant_environment_id'),
            tenant_namespace_id=_optional_int('tenant_namespace_id'),
            actor_user_id=int(current_user.id),
        )
    except (ValueError, ApiException, TenantAccessStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_access_grant_create_failed',
            status='error',
            title='Tenant Access Grant Failed',
            message=str(exc),
            metadata={'operation': 'create_access_grant'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_access_grant_created',
            status='success',
            title='Tenant Access Granted',
            message=f'{grant.membership.subject_name} received {grant.access_profile.replace("_", " ").title()} access.',
            detail=grant.reconciliation_message,
            metadata={'grant_id': grant.public_id, 'tenant_id': grant.tenant_id, 'operation': 'create_access_grant'},
        )
    return _tenant_section_redirect('access-grants')


@tenant_bp.post('/access-grants/<int:grant_id>/inspect')
@permission_required('tenant.manage')
def inspect_access_grant_route(grant_id: int):
    try:
        _csrf()
        grant = inspect_access_grant_by_id_committed(
            grant_id=grant_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_access_grant_inspect_failed',
            status='error',
            title='Tenant Access Inspection Failed',
            message=str(exc),
            metadata={'grant_id': grant_id, 'operation': 'inspect_access_grant'},
        )
    else:
        tone = 'success' if grant.reconciliation_status == 'ready' else 'warning'
        _record(
            event_type='kubernetes_tenant_access_grant_inspected',
            status=tone,
            title='Tenant Access Inspected',
            message=grant.reconciliation_message or 'Kubernetes RBAC inspection completed.',
            metadata={'grant_id': grant.public_id, 'operation': 'inspect_access_grant'},
        )
    return _tenant_section_redirect('access-grants')


@tenant_bp.post('/access-grants/<int:grant_id>/reconcile')
@permission_required('tenant.manage')
def reconcile_access_grant_route(grant_id: int):
    try:
        _csrf()
        grant = reconcile_access_grant_by_id_committed(
            grant_id=grant_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_access_grant_reconcile_failed',
            status='error',
            title='Tenant Access Reconciliation Failed',
            message=str(exc),
            metadata={'grant_id': grant_id, 'operation': 'reconcile_access_grant'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_access_grant_reconciled',
            status='success',
            title='Tenant Access Reconciled',
            message=grant.reconciliation_message or 'Kubernetes RBAC matches committed Tenant access intent.',
            metadata={'grant_id': grant.public_id, 'operation': 'reconcile_access_grant'},
        )
    return _tenant_section_redirect('access-grants')


@tenant_bp.post('/access-grants/<int:grant_id>/revoke')
@permission_required('tenant.manage')
def revoke_access_grant_route(grant_id: int):
    try:
        _csrf()
        grant = revoke_access_grant_by_id_committed(
            grant_id=grant_id,
            actor_user_id=int(current_user.id),
        )
    except (ValueError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_access_grant_revoke_failed',
            status='error',
            title='Tenant Access Revoke Requires Attention',
            message=str(exc),
            metadata={'grant_id': grant_id, 'operation': 'revoke_access_grant'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_access_grant_revoked',
            status='success',
            title='Tenant Access Revoked',
            message='Effective Kubernetes RoleBinding access was removed.',
            metadata={'grant_id': grant.public_id, 'tenant_id': grant.tenant_id, 'operation': 'revoke_access_grant'},
        )
    return _tenant_section_redirect('access-grants')


@tenant_bp.get('/discovery/preflight')
@permission_required('tenant.manage')
def tenant_adoption_preflight_route():
    try:
        context = get_tenant_adoption_preflight_context(
            cluster_id=str(request.args.get('cluster_id') or ''),
            provider_key=str(request.args.get('provider_key') or ''),
            resource_name=str(request.args.get('resource_name') or ''),
        )
    except (ValueError, ApiException) as exc:
        rendered = render_template(
            'kubernetes/tenant/partials/_tenant_adoption_preflight_error.html',
            tenant_adoption_preflight_error=str(exc),
        )
    except Exception:
        current_app.logger.exception('Tenant Adoption Preflight live read failed.')
        rendered = render_template(
            'kubernetes/tenant/partials/_tenant_adoption_preflight_error.html',
            tenant_adoption_preflight_error=(
                'The live provider preflight could not be completed. Refresh Discovery and retry.'
            ),
        )
    else:
        rendered = render_template(
            'kubernetes/tenant/partials/_tenant_adoption_preflight.html',
            can_manage=True,
            **context,
        )

    response = make_response(rendered)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@tenant_bp.post('/discovery/adopt')
@permission_required('tenant.manage')
def adopt_discovered_tenant_route():
    try:
        _csrf()
        tenant, environment, namespace = adopt_discovered_tenant_committed(request.form)
    except (ValueError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_discovery_adoption_failed',
            status='error',
            title='Tenant Adoption Requires Attention',
            message=str(exc),
            detail='Discovery adoption is fail-closed. Governance takeover occurs only after provider-equivalent validation and read-back.',
            metadata={
                'cluster_id': request.form.get('cluster_id'),
                'provider_key': request.form.get('provider_key'),
                'resource_name': request.form.get('resource_name'),
                'operation': 'adopt_discovered_tenant',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_discovery_adopted',
            status='success',
            title='Tenant Adopted · Managed',
            message=(
                f'{tenant.name} is adopted into KAORI with supported governance controls managed immediately. '
                'Observed provider values are preserved as the initial managed baseline.'
            ),
            detail=(
                f'{environment.environment.title()} · '
                f'{tenant.provider_key.replace("_", " ").title()} · '
                f'Generation {tenant.generation}'
            ),
            metadata={
                'tenant_id': tenant.id,
                'cluster_id': tenant.cluster_id,
                'provider_key': tenant.provider_key,
                'tenant_generation': tenant.generation,
                'namespace_id': namespace.id if namespace is not None else None,
                'operation': 'adopt_discovered_tenant',
                'provider_mutation_performed': bool(
                    (tenant.provider_evidence_json or {}).get('provider_mutation_performed')
                ),
            },
        )
    return _tenant_section_redirect('discovery')


@tenant_bp.post('/tenants')
@permission_required('tenant.manage')
def create_tenant_route():
    try:
        _csrf()
        tenant, environment = create_tenant_committed(request.form)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_create_failed',
            status='error',
            title='Tenant Creation Failed',
            message=str(exc),
            metadata={'cluster_id': request.form.get('cluster_id'), 'operation': 'create_tenant'},
        )
    except TenantStateConflictError as exc:
        current_app.logger.exception('Tenant creation conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_create_failed',
            status='error',
            title='Tenant Creation Failed',
            message=str(exc),
            detail='Capsule provider creation is compensated when this request created the provider object before the database conflict.',
            metadata={'cluster_id': request.form.get('cluster_id'), 'operation': 'create_tenant'},
        )
    else:
        provider_label = 'Capsule' if tenant.provider_key == 'capsule' else 'Native Kubernetes'
        _record(
            event_type='kubernetes_tenant_created',
            status='success',
            title='Tenant Created',
            message=(
                f'{tenant.name} is governed with Capsule provider authority.'
                if tenant.provider_key == 'capsule'
                else f'{tenant.name} is ready for Native Kubernetes namespace provisioning.'
            ),
            detail=f'{environment.environment.title()} · {provider_label}',
            metadata={
                'tenant_id': tenant.id,
                'cluster_id': tenant.cluster_id,
                'environment': environment.environment,
                'provider_key': tenant.provider_key,
                'provider_reference': tenant.provider_reference,
                'operation': 'create_tenant',
            },
        )
    return _tenant_section_redirect('tenant-setup')


@tenant_bp.post('/tenants/<string:tenant_id>/decommission')
@permission_required('tenant.manage')
def decommission_tenant_route(tenant_id: str):
    try:
        _csrf()
        preflight = request_tenant_decommission_committed(
            tenant_id=tenant_id,
            actor=cast(User, current_user),
        )
        dispatch = dispatch_tenant_decommission(
            tenant_id=tenant_id,
            requested_by_user_id=int(current_user.id),
        )
    except (ValueError, TenantDecommissionBlocked) as exc:
        _record(
            event_type='kubernetes_tenant_decommission_blocked',
            status='error',
            title='Tenant Decommission Blocked',
            message=str(exc),
            detail='No provider-authority bypass was performed.',
            metadata={'tenant_id': tenant_id, 'operation': 'decommission_tenant'},
        )
    except Exception as exc:
        current_app.logger.exception('Tenant decommission dispatch failed.')
        _record(
            event_type='kubernetes_tenant_decommission_dispatch_failed',
            status='error',
            title='Tenant Decommission Queue Failed',
            message=str(exc),
            detail='The Tenant remains frozen in Decommissioning state; retry after restoring the runtime worker.',
            metadata={'tenant_id': tenant_id, 'operation': 'decommission_tenant'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_decommission_queued',
            status='success' if dispatch.created else 'info',
            title='Tenant Decommission Queued' if dispatch.created else 'Tenant Decommission Already Active',
            message=dispatch.message,
            detail=(
                f'Generation {preflight["tenant_generation"]} · '
                f'{preflight["credential_count"]} credentials · '
                f'{preflight["access_grant_count"]} grants · '
                f'{preflight["namespace_count"]} namespaces'
            ),
            metadata={
                'tenant_id': tenant_id,
                'job_public_id': dispatch.job.public_id if dispatch.job is not None else None,
                'operation': 'decommission_tenant',
            },
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/resource-profiles')
@permission_required('tenant.manage')
def create_resource_profile_route():
    try:
        _csrf()
        profile = create_resource_profile_committed(request.form)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_resource_profile_create_failed',
            status='error',
            title='Resource Profile Creation Failed',
            message=str(exc),
            metadata={'operation': 'create_resource_profile'},
        )
    except TenantStateConflictError as exc:
        current_app.logger.exception('Tenant Resource Profile creation conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_resource_profile_create_failed',
            status='error',
            title='Resource Profile Creation Failed',
            message=str(exc),
            metadata={'operation': 'create_resource_profile'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_resource_profile_created',
            status='success',
            title='Resource Profile Created',
            message=f'{profile.name} is available for Tenant namespace provisioning.',
            detail=profile.profile_class.title(),
            metadata={
                'resource_profile_id': profile.public_id,
                'profile_class': profile.profile_class,
                'operation': 'create_resource_profile',
            },
        )
    return redirect(url_for('tenant.resource_profiles', view='profiles'))


@tenant_bp.post('/resource-profiles/<int:profile_id>/edit')
@permission_required('tenant.manage')
def update_resource_profile_route(profile_id: int):
    try:
        _csrf()
        profile, contract_changed = update_resource_profile_committed(profile_id, request.form)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_resource_profile_update_failed',
            status='error',
            title='Resource Profile Update Failed',
            message=str(exc),
            metadata={'resource_profile_id': profile_id, 'operation': 'update_resource_profile'},
        )
    except TenantStateConflictError as exc:
        current_app.logger.exception('Tenant Resource Profile update conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_resource_profile_update_failed',
            status='error',
            title='Resource Profile Update Failed',
            message=str(exc),
            metadata={'resource_profile_id': profile_id, 'operation': 'update_resource_profile'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_resource_profile_updated',
            status='success',
            title='Resource Profile Updated',
            message=(
                f'{profile.name} contract updated to v{profile.version}. Existing Namespace snapshots are unchanged.'
                if contract_changed
                else f'{profile.name} metadata/state updated. Allocation contract remains v{profile.version}.'
            ),
            detail=(
                'Custom Resource Profile'
                if profile.profile_class == 'custom'
                else 'KAORI Built-in Preset · Versioned Controls'
            ),
            metadata={
                'resource_profile_id': profile.public_id,
                'profile_class': profile.profile_class,
                'resource_profile_version': profile.version,
                'contract_changed': contract_changed,
                'operation': 'update_resource_profile',
            },
        )
    return redirect(url_for('tenant.resource_profiles', view='profiles'))


@tenant_bp.post('/resource-profiles/<int:profile_id>/rollout')
@permission_required('tenant.manage')
def rollout_resource_profile_route(profile_id: int):
    try:
        _csrf()
        summary = rollout_resource_profile_to_tenant_committed(
            profile_id=profile_id,
            tenant_id=str(request.form.get('tenant_id') or ''),
        )
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_resource_profile_rollout_failed',
            status='error',
            title='Resource Profile Rollout Failed',
            message=str(exc),
            metadata={'resource_profile_id': profile_id, 'operation': 'rollout_resource_profile'},
        )
    else:
        failed = list(summary.get('failed') or [])
        status = 'warning' if failed else 'success'
        _record(
            event_type='kubernetes_tenant_resource_profile_rollout_completed',
            status=status,
            title='Resource Profile Rollout Completed'
            if not failed
            else 'Resource Profile Rollout Partially Completed',
            message=(
                f'{summary["profile_name"]} v{summary["profile_version"]}: '
                f'{summary["updated"]} Namespace(s) updated, '
                f'{summary["already_current"]} already current' + (f', {len(failed)} blocked.' if failed else '.')
            ),
            detail=f'Tenant {summary["tenant_name"]}',
            metadata={
                'resource_profile_id': summary['profile_id'],
                'resource_profile_version': summary['profile_version'],
                'tenant_id': summary['tenant_id'],
                'updated_namespaces': summary['updated'],
                'already_current_namespaces': summary['already_current'],
                'failed_namespaces': failed,
                'operation': 'rollout_resource_profile',
            },
        )
    return redirect(url_for('tenant.resource_profiles', view='profiles'))


@tenant_bp.post('/resource-profiles/<int:profile_id>/delete')
@permission_required('tenant.manage')
def delete_resource_profile_route(profile_id: int):
    try:
        _csrf()
        deleted = delete_resource_profile_committed(profile_id)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_resource_profile_delete_failed',
            status='error',
            title='Resource Profile Delete Blocked',
            message=str(exc),
            metadata={'resource_profile_id': profile_id, 'operation': 'delete_resource_profile'},
        )
    except TenantStateConflictError as exc:
        current_app.logger.exception('Tenant Resource Profile deletion conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_resource_profile_delete_failed',
            status='error',
            title='Resource Profile Delete Failed',
            message=str(exc),
            metadata={'resource_profile_id': profile_id, 'operation': 'delete_resource_profile'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_resource_profile_deleted',
            status='success',
            title='Resource Profile Deleted',
            message=f'{deleted["name"]} was deleted after dependency verification.',
            detail=f'Custom · v{deleted["version"]}',
            metadata={
                'resource_profile_id': deleted['public_id'],
                'profile_class': deleted['profile_class'],
                'resource_profile_version': deleted['version'],
                'operation': 'delete_resource_profile',
            },
        )
    return redirect(url_for('tenant.resource_profiles', view='profiles'))


@tenant_bp.post('/capacity-policy')
@permission_required('tenant.manage')
def update_capacity_policy_route():
    try:
        _csrf()
        policy = upsert_capacity_policy_committed(request.form)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_capacity_policy_update_failed',
            status='error',
            title='Tenant Capacity Policy Update Failed',
            message=str(exc),
            metadata={
                'cluster_id': request.form.get('capacity_cluster_id'),
                'operation': 'update_capacity_policy',
            },
        )
    except TenantCapacityStateConflictError as exc:
        current_app.logger.exception('Tenant Capacity Governance policy update conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_capacity_policy_update_failed',
            status='error',
            title='Tenant Capacity Policy Update Failed',
            message=str(exc),
            metadata={
                'cluster_id': request.form.get('capacity_cluster_id'),
                'operation': 'update_capacity_policy',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_capacity_policy_updated',
            status='success',
            title='Tenant Capacity Policy Updated',
            message='Tenant Allocation Budget inputs were committed for the selected cluster.',
            detail=f'Safety headroom {policy.safety_headroom_percent}%',
            metadata={
                'cluster_id': policy.cluster_id,
                'safety_headroom_percent': policy.safety_headroom_percent,
                'operation': 'update_capacity_policy',
            },
        )
    return redirect(url_for('tenant.resource_profiles', view='capacity'))


@tenant_bp.post('/shared-allocation/cutover')
@permission_required('tenant.manage')
def cutover_capsule_shared_allocation_route():
    try:
        _csrf()
        intent = cutover_capsule_global_quota_allocation_committed(
            tenant_id=str(request.form.get('tenant_id') or ''),
            profile_id=_required_int('resource_profile_id'),
        )
    except (ValueError, ApiException, CapsuleSharedAllocationStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_shared_allocation_cutover_failed',
            status='error',
            title='Capsule Shared Allocation Cutover Failed',
            message=str(exc),
            detail='Capsule remains authoritative; KAORI does not fall back to Native quota mutation.',
            metadata={
                'tenant_id': request.form.get('tenant_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'operation': 'capsule_shared_allocation_cutover',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_shared_allocation_cutover_completed',
            status='success',
            title='Capsule Shared Allocation Governance Enabled',
            message=f'{intent.tenant.name} shared allocation is now KAORI Managed through GlobalResourceQuota.',
            metadata={
                'tenant_id': intent.tenant_id,
                'advanced_intent_id': intent.id,
                'advanced_intent_public_id': intent.public_id,
                'resource_name': intent.resource_name,
                'operation': 'capsule_shared_allocation_cutover',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning', view='allocation'))


@tenant_bp.post('/shared-allocation/<int:intent_id>/reapply')
@permission_required('tenant.manage')
def reapply_capsule_shared_allocation_route(intent_id: int):
    try:
        _csrf()
        intent = reapply_capsule_shared_allocation_intent_committed(intent_id=intent_id)
    except (ValueError, ApiException, CapsuleSharedAllocationStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_shared_allocation_reapply_failed',
            status='error',
            title='Capsule Shared Allocation Reapply Failed',
            message=str(exc),
            metadata={'advanced_intent_id': intent_id, 'operation': 'reapply_kaori_intent'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_shared_allocation_reapplied',
            status='success',
            title='KAORI Shared Allocation Reapplied',
            message=f'{intent.tenant.name} GlobalResourceQuota matches committed KAORI intent.',
            metadata={
                'tenant_id': intent.tenant_id,
                'advanced_intent_id': intent.id,
                'operation': 'reapply_kaori_intent',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/shared-allocation/<int:intent_id>/accept-provider-state')
@permission_required('tenant.manage')
def accept_capsule_shared_provider_allocation_route(intent_id: int):
    try:
        _csrf()
        intent = accept_capsule_shared_provider_state_committed(intent_id=intent_id)
    except (ValueError, ApiException, CapsuleSharedAllocationStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_shared_allocation_accept_failed',
            status='error',
            title='Capsule Provider State Acceptance Failed',
            message=str(exc),
            metadata={'advanced_intent_id': intent_id, 'operation': 'accept_provider_state'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_shared_allocation_provider_state_accepted',
            status='success',
            title='Capsule Provider State Accepted',
            message=f'{intent.tenant.name} live GlobalResourceQuota is now the governed KAORI intent.',
            metadata={
                'tenant_id': intent.tenant_id,
                'advanced_intent_id': intent.id,
                'operation': 'accept_provider_state',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/tenant-quota/cutover')
@permission_required('tenant.manage')
def cutover_capsule_tenant_quota_route():
    try:
        _csrf()
        tenant = cutover_capsule_tenant_resource_quota_committed(
            tenant_id=str(request.form.get('tenant_id') or ''),
            profile_id=_required_int('resource_profile_id'),
        )
    except (ValueError, ApiException, CapsuleTenantQuotaStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_cutover_failed',
            status='error',
            title='Capsule Tenant Quota Cutover Failed',
            message=str(exc),
            detail='Capsule remains authoritative; KAORI never substitutes a Native ResourceQuota write.',
            metadata={
                'tenant_id': request.form.get('tenant_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'operation': 'capsule_tenant_quota_cutover',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_cutover_completed',
            status='success',
            title='Capsule Tenant Quota Governance Enabled',
            message=f'{tenant.name} allocation is now KAORI Managed through Tenant.spec.resourceQuotas.',
            metadata={
                'tenant_id': tenant.id,
                'operation': 'capsule_tenant_quota_cutover',
                'allocation_authority': 'capsule_tenant_resource_quotas',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning', view='allocation'))


@tenant_bp.post('/tenant-quota/change')
@permission_required('tenant.manage')
def change_capsule_tenant_quota_route():
    try:
        _csrf()
        tenant = change_capsule_tenant_resource_quota_committed(
            tenant_id=str(request.form.get('tenant_id') or ''),
            profile_id=_required_int('resource_profile_id'),
        )
    except (ValueError, ApiException, CapsuleTenantQuotaStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_change_failed',
            status='error',
            title='Capsule Tenant Allocation Change Failed',
            message=str(exc),
            detail='Existing KAORI intent remains committed unless provider mutation and read-back both succeed.',
            metadata={
                'tenant_id': request.form.get('tenant_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'operation': 'capsule_tenant_quota_change',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_changed',
            status='success',
            title='Capsule Tenant Allocation Changed',
            message=f'{tenant.name} Tenant.spec.resourceQuotas matches the new governed allocation.',
            metadata={
                'tenant_id': tenant.id,
                'operation': 'capsule_tenant_quota_change',
                'allocation_authority': 'capsule_tenant_resource_quotas',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning', view='allocation'))


@tenant_bp.post('/tenant-quota/<string:tenant_id>/reapply')
@permission_required('tenant.manage')
def reapply_capsule_tenant_quota_route(tenant_id: str):
    try:
        _csrf()
        tenant = reapply_capsule_tenant_quota_intent_committed(tenant_id=tenant_id)
    except (ValueError, ApiException, CapsuleTenantQuotaStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_reapply_failed',
            status='error',
            title='Capsule Tenant Quota Reapply Failed',
            message=str(exc),
            metadata={'tenant_id': tenant_id, 'operation': 'reapply_kaori_intent'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_reapplied',
            status='success',
            title='KAORI Tenant Quota Intent Reapplied',
            message=f'{tenant.name} Tenant.spec.resourceQuotas matches committed KAORI intent.',
            metadata={
                'tenant_id': tenant.id,
                'operation': 'reapply_kaori_intent',
                'allocation_authority': 'capsule_tenant_resource_quotas',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/tenant-quota/<string:tenant_id>/accept-provider-state')
@permission_required('tenant.manage')
def accept_capsule_tenant_provider_state_route(tenant_id: str):
    try:
        _csrf()
        tenant = accept_capsule_tenant_provider_state_committed(tenant_id=tenant_id)
    except (ValueError, ApiException, CapsuleTenantQuotaStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_accept_failed',
            status='error',
            title='Capsule Tenant Provider State Acceptance Failed',
            message=str(exc),
            metadata={'tenant_id': tenant_id, 'operation': 'accept_provider_state'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_capsule_tenant_quota_provider_state_accepted',
            status='success',
            title='Capsule Tenant Provider State Accepted',
            message=f'{tenant.name} live Tenant.spec.resourceQuotas is now the governed KAORI intent.',
            metadata={
                'tenant_id': tenant.id,
                'operation': 'accept_provider_state',
                'allocation_authority': 'capsule_tenant_resource_quotas',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/namespace-allocation/cutover')
@permission_required('tenant.manage')
def cutover_namespace_allocation_route():
    try:
        _csrf()
        record = cutover_adopted_namespace_allocation_committed(request.form)
    except (ValueError, ApiException, TenantStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_allocation_cutover_failed',
            status='error',
            title='Allocation Governance Cutover Failed',
            message=str(exc),
            detail='Adopted provider state remains authoritative unless provider mutation and read-back both succeed.',
            metadata={
                'tenant_namespace_id': request.form.get('tenant_namespace_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'operation': 'allocation_governance_cutover',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_allocation_cutover_completed',
            status='success',
            title='Allocation Governance Cutover Completed',
            message=f'{record.namespace} allocation is now KAORI Managed.',
            detail=record.provisioning_message,
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'resource_profile_id': record.resource_profile_id,
                'capacity_decision_id': record.capacity_decision_id,
                'namespace_ownership_status': record.ownership_status,
                'allocation_control_state': 'kaori_managed',
                'operation': 'allocation_governance_cutover',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning', view='allocation'))


@tenant_bp.post('/namespace-allocation')
@permission_required('tenant.manage')
def change_namespace_allocation_route():
    try:
        _csrf()
        record = change_native_namespace_allocation_committed(request.form)
    except (ValueError, ApiException, TenantStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_namespace_allocation_change_failed',
            status='error',
            title='Tenant Allocation Change Failed',
            message=str(exc),
            metadata={
                'tenant_namespace_id': request.form.get('tenant_namespace_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'operation': 'change_namespace_allocation',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_namespace_allocation_changed',
            status='success' if record.provisioning_status == 'ready' else 'warning',
            title='Tenant Allocation Changed',
            message=f'{record.namespace} finished with {record.provisioning_status.title()} state.',
            detail=record.provisioning_message,
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'resource_profile_id': record.resource_profile_id,
                'capacity_decision_id': record.capacity_decision_id,
                'provisioning_status': record.provisioning_status,
                'operation': 'change_namespace_allocation',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning'))


@tenant_bp.post('/namespaces')
@permission_required('tenant.manage')
def provision_namespace_route():
    try:
        _csrf()
        record = provision_native_namespace_committed(request.form)
    except (ValueError, ApiException, TenantStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_namespace_provision_failed',
            status='error',
            title='Tenant Namespace Provisioning Failed',
            message=str(exc),
            metadata={
                'tenant_environment_id': request.form.get('tenant_environment_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'namespace': request.form.get('namespace'),
                'operation': 'provision_namespace',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_namespace_provisioned',
            status='success' if record.provisioning_status == 'ready' else 'warning',
            title='Tenant Namespace Provisioned',
            message=f'{record.namespace} finished with {record.provisioning_status.title()} state.',
            detail=record.provisioning_message,
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'provisioning_status': record.provisioning_status,
                'operation': 'provision_namespace',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning'))


@tenant_bp.post('/namespaces/<int:namespace_id>/allocation/reapply')
@permission_required('tenant.manage')
def reapply_namespace_allocation_route(namespace_id: int):
    try:
        _csrf()
        record = reapply_kaori_allocation_intent_committed(namespace_id=namespace_id)
    except (ValueError, RuntimeError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_allocation_reapply_failed',
            status='error',
            title='Reapply KAORI Intent Failed',
            message=str(exc),
            detail=(
                'Committed desired allocation remains unchanged; review fresh provider drift evidence before retrying.'
            ),
            metadata={
                'tenant_namespace_id': namespace_id,
                'operation': 'reapply_kaori_allocation_intent',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_allocation_reapplied',
            status='success',
            title='KAORI Allocation Intent Reapplied',
            message=f'{record.namespace} matches the committed KAORI allocation again.',
            detail=record.provisioning_message,
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'capacity_decision_id': record.capacity_decision_id,
                'allocation_control_state': 'kaori_managed',
                'operation': 'reapply_kaori_allocation_intent',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/namespaces/<int:namespace_id>/allocation/accept-provider-state')
@permission_required('tenant.manage')
def accept_namespace_provider_allocation_route(namespace_id: int):
    try:
        _csrf()
        record = accept_provider_allocation_state_committed(namespace_id=namespace_id)
    except (ValueError, RuntimeError, ApiException) as exc:
        _record(
            event_type='kubernetes_tenant_allocation_accept_provider_failed',
            status='error',
            title='Accept Provider State Failed',
            message=str(exc),
            detail='KAORI desired allocation was not changed.',
            metadata={
                'tenant_namespace_id': namespace_id,
                'operation': 'accept_provider_allocation_state',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_allocation_provider_state_accepted',
            status='success',
            title='Provider Allocation State Accepted',
            message=f'{record.namespace} provider allocation is now the governed KAORI intent.',
            detail='No provider write was required; the current live allocation passed governance checks.',
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'capacity_decision_id': record.capacity_decision_id,
                'allocation_control_state': 'kaori_managed',
                'provider_mutation_performed': False,
                'operation': 'accept_provider_allocation_state',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/namespaces/<int:namespace_id>/reconcile')
@permission_required('tenant.manage')
def reconcile_namespace_route(namespace_id: int):
    try:
        _csrf()
        record = reconcile_managed_native_namespace_committed(namespace_id=namespace_id)
    except (ValueError, ApiException, TenantStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_namespace_reconcile_failed',
            status='error',
            title='Namespace Reconciliation Failed',
            message=str(exc),
            metadata={
                'tenant_namespace_id': namespace_id,
                'operation': 'reconcile_namespace',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_namespace_reconciled',
            status='success' if record.provisioning_status == 'ready' else 'warning',
            title='Namespace Reconciled',
            message=f'{record.namespace} was restored from committed Tenant intent.',
            detail=record.provisioning_message,
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'provisioning_status': record.provisioning_status,
                'operation': 'reconcile_namespace',
            },
        )
    return redirect(url_for('tenant.operations', tab='drift-reconcile'))


@tenant_bp.post('/credentials/human')
@permission_required('tenant.manage')
def create_human_credential_route():
    try:
        _csrf()
        credential = create_human_credential_from_grant_committed(
            access_grant_id=_required_int('access_grant_id'),
            request=HumanCredentialIssueRequest(
                jumpserver_reference=str(request.form.get('jumpserver_reference') or ''),
                purpose=str(request.form.get('purpose') or 'interactive'),
            ),
            actor=cast(User, current_user),
        )
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_credential_issue_failed',
            status='error',
            title='Tenant Human Credential Requires Attention',
            message=str(exc),
            metadata={'operation': 'credential_issue_human'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_credential_issued',
            status='success',
            title='Tenant Human Credential Issued',
            message=f'{credential.service_account_name} is ready for governed JumpServer delivery.',
            metadata={
                'credential_id': credential.id,
                'credential_public_id': credential.public_id,
                'operation': 'credential_issue_human',
            },
        )
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/deployer')
@permission_required('tenant.manage')
def create_deployer_credential_route():
    try:
        _csrf()
        credential = create_deployer_credential_committed(
            tenant_namespace_id=_required_int('tenant_namespace_id'),
            owner_user_id=_required_int('owner_user_id'),
            request=DeployerCredentialIssueRequest(
                application_name=str(request.form.get('application_name') or ''),
                purpose=str(request.form.get('purpose') or 'github-actions-helm'),
            ),
            actor=cast(User, current_user),
        )
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_deployer_credential_issue_failed',
            status='error',
            title='Tenant Deployer Credential Requires Attention',
            message=str(exc),
            metadata={'operation': 'credential_issue_deployer'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_deployer_credential_issued',
            status='success',
            title='Tenant Deployer Credential Issued',
            message=f'{credential.service_account_name} is ready for governed CI/CD delivery.',
            metadata={
                'credential_id': credential.id,
                'credential_public_id': credential.public_id,
                'operation': 'credential_issue_deployer',
            },
        )
    return _tenant_section_redirect('credentials')


def _credential_feedback(
    *,
    action: str,
    credential_id: int,
    operation: Callable[..., TenantCredential],
) -> None:
    try:
        _csrf()
        credential = operation(credential_id=credential_id, actor=current_user)
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type=f'kubernetes_tenant_credential_{action}_failed',
            status='error',
            title=f'Tenant Credential {action.title()} Requires Attention',
            message=str(exc),
            metadata={'credential_id': credential_id, 'operation': f'credential_{action}'},
        )
    else:
        _record(
            event_type=f'kubernetes_tenant_credential_{action}',
            status='success',
            title=f'Tenant Credential {action.title()}',
            message=f'{credential.service_account_name} is now {credential.status.replace("_", " ")}.',
            metadata={
                'credential_id': credential.id,
                'credential_public_id': credential.public_id,
                'operation': f'credential_{action}',
            },
        )


@tenant_bp.post('/credentials/<int:credential_id>/material')
@permission_required('tenant.manage')
def generate_credential_material_route(credential_id: int):
    try:
        _csrf()
        requested_seconds = _required_int('requested_seconds')
        material = generate_credential_material_committed(
            credential_id=credential_id,
            namespace_id=_required_int('namespace_id'),
            requested_seconds=requested_seconds,
            actor=cast(User, current_user),
        )
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_credential_material_failed',
            status='error',
            title='Credential Material Requires Attention',
            message=str(exc),
            metadata={'credential_id': credential_id, 'operation': 'credential_material_generate'},
        )
        return _tenant_section_redirect('credentials')

    context = _tenant_workspace_context()
    if isinstance(material, GeneratedTokenMaterial):
        material_kind = 'token'
        material_title = 'JumpServer ServiceAccount Token'
        material_value = material.token
        material_base64 = None
        delivery_label = 'Manual JumpServer delivery'
        page_title = 'One-Time Human Token'
        page_icon = 'user-key'
    elif isinstance(material, GeneratedKubeconfigMaterial):
        material_kind = 'kubeconfig'
        material_title = 'CI/CD Kubeconfig'
        material_value = material.kubeconfig
        material_base64 = base64.b64encode(material.kubeconfig.encode('utf-8')).decode('ascii')
        delivery_label = 'GitHub Actions / Helm'
        page_title = 'One-Time CI/CD Kubeconfig'
        page_icon = 'git-branch'
    else:
        abort(500)

    response = make_response(
        render_template(
            'kubernetes/tenant/credential_material.html',
            tenant_page='tenants',
            tenant_page_title=page_title,
            tenant_page_icon=page_icon,
            material_kind=material_kind,
            material_title=material_title,
            material_value=material_value,
            material_base64=material_base64,
            material_namespace=material.namespace,
            material_expires_at=material.expires_at,
            material_requested_seconds=requested_seconds,
            material_access_package=material.access_package,
            material_credential_valid_until=material.expires_at,
            delivery_label=delivery_label,
            **context,
        )
    )
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


@tenant_bp.post('/credentials/<int:credential_id>/renew')
@permission_required('tenant.manage')
def renew_credential_route(credential_id: int):
    _credential_feedback(action='renewed', credential_id=credential_id, operation=renew_credential_committed)
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/<int:credential_id>/suspend')
@permission_required('tenant.manage')
def suspend_credential_route(credential_id: int):
    _credential_feedback(action='suspended', credential_id=credential_id, operation=suspend_credential_committed)
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/<int:credential_id>/resume')
@permission_required('tenant.manage')
def resume_credential_route(credential_id: int):
    _credential_feedback(action='resumed', credential_id=credential_id, operation=resume_credential_committed)
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/<int:credential_id>/revoke')
@permission_required('tenant.manage')
def revoke_credential_route(credential_id: int):
    _credential_feedback(action='revoked', credential_id=credential_id, operation=revoke_credential_committed)
    return _tenant_section_redirect('credentials')
