from __future__ import annotations

import json
from typing import Any, cast

from flask import abort, current_app, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from kubernetes.client.rest import ApiException

from app.access.rbac.decorators import any_permission_required, permission_required
from app.common.pagination import paginate_sequence
from app.kubernetes.tenant import routes_access as _routes_access
from app.kubernetes.tenant import routes_credentials as _routes_credentials
from app.kubernetes.tenant.admin_workspace import (
    get_access_grant_registry_context,
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
from app.kubernetes.tenant.decommission_service import (
    TenantDecommissionBlocked,
    request_tenant_decommission_committed,
)
from app.kubernetes.tenant.discovery_adoption import (
    adopt_discovered_tenant_committed,
    attach_discovered_native_namespace_committed,
)
from app.kubernetes.tenant.discovery_service import get_tenant_adoption_preflight_context
from app.kubernetes.tenant.job_adapter import (
    build_tenant_sync_state,
    dispatch_tenant_decommission,
    get_visible_tenant_sync_job,
)
from app.kubernetes.tenant.live_connection import get_live_tenant_connection_context
from app.kubernetes.tenant.native_handoff_dry_run import (
    dry_run_native_release_handoff_committed,
)
from app.kubernetes.tenant.native_handoff_readback import (
    observe_external_native_handoff_committed,
)
from app.kubernetes.tenant.overview import dispatch_tenant_inventory_sync
from app.kubernetes.tenant.release_handoff_approval import (
    approve_release_handoff_plan_committed,
    prepare_release_handoff_plan_committed,
)
from app.kubernetes.tenant.release_preflight import (
    release_adopted_tenant_committed,
    review_tenant_release_preflight_committed,
)
from app.kubernetes.tenant.release_successor_claim import (
    record_release_successor_claim_committed,
)
from app.kubernetes.tenant.route_common import (
    _csrf,
    _operations_active_tab,
    _operations_provisioning_context,
    _record,
    _required_int,
    _tenant_active_section_context,
    _tenant_admin_section,
    _tenant_admin_support_context,
    _tenant_section_redirect,
    _tenant_workspace_context,
    tenant_bp,
)
from app.kubernetes.tenant.service import (
    TenantStateConflictError,
    change_native_namespace_allocation_committed,
    create_resource_profile_committed,
    create_tenant_committed,
    cutover_adopted_namespace_allocation_committed,
    delete_resource_profile_committed,
    get_capacity_decision_registry_context,
    get_namespace_provisioning_support_context,
    get_namespace_registry_context,
    get_resource_profile_registry_context,
    get_resource_profile_workspace_context,
    get_tenant_registry_context,
    provision_native_namespace_committed,
    reconcile_managed_native_namespace_committed,
    rollout_resource_profile_to_tenant_committed,
    update_resource_profile_committed,
)
from app.kubernetes.tenant.workspace import (
    get_tenant_cluster_estate_context,
    get_tenant_operations_evidence_context,
    get_tenant_operations_summary_context,
    get_tenant_overview_context,
    get_tenant_sync_workspace_context,
)
from app.models import User
from app.platform_operations.notifications.service import queue_transient_feedback


@tenant_bp.get('/')
@any_permission_required('tenant.view', 'tenant.manage')
def index():
    context = _tenant_workspace_context(include_sync=False)
    context.update(get_tenant_overview_context())
    context['tenant_cluster_page'] = request.args.get('cluster_page', 1, type=int) or 1
    context['tenant_cluster_per_page'] = request.args.get('cluster_per_page', 5, type=int) or 5
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


@tenant_bp.get('/tenants')
@any_permission_required('tenant.view', 'tenant.manage')
def tenants():
    active_section = _tenant_admin_section(request.args.get('section'))
    context = _tenant_workspace_context()
    context.update(get_tenant_summary_context())
    context.update(_tenant_admin_support_context(active_section))
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
    context.update(get_resource_profile_workspace_context())
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
    context.update(get_namespace_provisioning_support_context())
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


def _operations_drift_context() -> dict[str, Any]:
    drift_context = get_namespace_registry_context(
        page=request.args.get('ops_drift_page', 1, type=int) or 1,
        per_page=request.args.get('ops_drift_per_page', 5, type=int) or 5,
        search=str(request.args.get('ops_drift_search') or ''),
        tenant_id=str(request.args.get('ops_drift_tenant_id') or ''),
        environment=str(request.args.get('ops_drift_environment') or ''),
        status='drifted',
        include_workflow_support=False,
    )
    provider_context = get_tenant_registry_context(
        page=request.args.get('ops_provider_page', 1, type=int) or 1,
        per_page=request.args.get('ops_provider_per_page', 5, type=int) or 5,
        search=str(request.args.get('ops_provider_search') or ''),
        cluster_id=str(request.args.get('ops_provider_cluster_id') or ''),
        environment=str(request.args.get('ops_provider_environment') or ''),
        lifecycle_status=str(request.args.get('ops_provider_lifecycle') or ''),
        include_decommission_preflight=False,
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
    context = get_capsule_shared_allocation_context(
        drift_page=request.args.get('ops_capsule_shared_page', 1, type=int) or 1,
        drift_per_page=request.args.get('ops_capsule_shared_per_page', 5, type=int) or 5,
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
    return context


@tenant_bp.get('/operations')
@any_permission_required('tenant.view', 'tenant.manage')
def operations():
    active_tab = _operations_active_tab()
    context = _tenant_workspace_context()
    context.update(get_tenant_operations_summary_context())
    if active_tab == 'provisioning':
        context.update(_operations_provisioning_context())
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
    elif active_tab in {'allocation-drift', 'operational-reconcile'}:
        context.update(_operations_drift_context())

    return render_template(
        'kubernetes/tenant/operations.html',
        tenant_page='operations',
        tenant_page_title='Operations',
        tenant_page_icon='activity',
        active_tab=active_tab,
        can_manage=current_user.has_permission('tenant.manage'),
        **context,
    )


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
        attach_existing = bool(str(request.form.get('attach_environment_id') or '').strip())
        if attach_existing:
            tenant, environment, namespace = attach_discovered_native_namespace_committed(request.form)
        else:
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
                f'{namespace.namespace} was attached to existing Tenant {tenant.name} with governed allocation.'
                if attach_existing and namespace is not None else
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
                'operation': 'attach_existing_tenant_namespace' if attach_existing else 'adopt_discovered_tenant',
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


@tenant_bp.post('/tenants/<string:tenant_id>/release-preflight')
@permission_required('tenant.manage')
def review_tenant_release_route(tenant_id: str):
    try:
        _csrf()
        result = review_tenant_release_preflight_committed(
            tenant_id=tenant_id, actor_user_id=int(current_user.id)
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_release_preflight_failed',
            status='error',
            title='Release Governance Review Unavailable',
            message=str(exc),
            detail='No Tenant, Namespace or RBAC was released.',
            metadata={'tenant_id': tenant_id, 'operation': 'review_tenant_release'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_release_preflight_reviewed',
            status='warning' if result['blockers'] else 'info',
            title='Release Governance Preflight Recorded',
            message=f"{len(result['blockers'])} blocker(s); no provider resource was modified.",
            detail='Release is not yet admitted. Review the committed dependency and provider handoff evidence.',
            metadata={'tenant_id': tenant_id, 'operation': 'review_tenant_release'},
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/prepare')
@permission_required('tenant.manage')
@permission_required('integrations.manage')
def prepare_tenant_release_handoff_route(tenant_id: str):
    try:
        _csrf()
        result = prepare_release_handoff_plan_committed(
            tenant_id=tenant_id,
            actor_user_id=int(current_user.id),
            successor_owner=str(request.form.get('successor_owner') or ''),
            change_reference=str(request.form.get('change_reference') or ''),
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_release_handoff_plan_blocked',
            status='warning',
            title='Handoff Plan Not Prepared',
            message=str(exc),
            detail='Release governance and provider ownership remain unchanged.',
            metadata={'tenant_id': tenant_id, 'operation': 'prepare_release_handoff'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_release_handoff_plan_prepared',
            status='info',
            title='Handoff Plan Prepared',
            message=f"Successor {result['successor_owner']} · {result['change_reference']}",
            detail='Independent approval and provider ownership transfer are still required.',
            metadata={'tenant_id': tenant_id, 'operation': 'prepare_release_handoff'},
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/approve')
@permission_required('tenant.manage')
@permission_required('integrations.manage')
def approve_tenant_release_handoff_route(tenant_id: str):
    try:
        _csrf()
        if request.form.get('confirm_handoff_approval') != 'approved':
            raise ValueError('Independent handoff acknowledgement must be explicit.')
        result = approve_release_handoff_plan_committed(
            tenant_id=tenant_id,
            actor_user_id=int(current_user.id),
            plan_sha256=str(request.form.get('plan_sha256') or ''),
            approved=True,
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_release_handoff_approval_blocked',
            status='warning',
            title='Handoff Approval Blocked',
            message=str(exc),
            detail='No provider mutation was attempted; Release is not unlocked.',
            metadata={'tenant_id': tenant_id, 'operation': 'approve_release_handoff'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_release_handoff_acknowledged',
            status='info',
            title='Independent Handoff Review Recorded',
            message=f"Review recorded for {result['successor_owner']}; external transfer remains pending.",
            detail='Provider read-back and a separately admitted transfer executor are still required.',
            metadata={'tenant_id': tenant_id, 'operation': 'approve_release_handoff'},
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/successor-reference')
@permission_required('tenant.manage')
@permission_required('integrations.manage')
def record_tenant_release_successor_reference_route(tenant_id: str):
    try:
        _csrf()
        if request.form.get('confirm_successor_reference') != 'record':
            raise ValueError('Explicit unverified external reference acknowledgement is required.')
        result = record_release_successor_claim_committed(
            tenant_id=tenant_id,
            actor_user_id=int(current_user.id),
            plan_sha256=str(request.form.get('plan_sha256') or ''),
            successor_reference=str(request.form.get('successor_reference') or ''),
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_release_successor_reference_blocked',
            status='warning', title='External Successor Reference Not Recorded',
            message=str(exc),
            detail='Provider ownership and Release authority remain unchanged.',
            metadata={'tenant_id': tenant_id, 'operation': 'successor_reference'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_release_successor_reference_recorded',
            status='info', title='Unverified Successor Reference Recorded',
            message=f"External reference {result['successor_reference']} recorded for review.",
            detail='Not verified acceptance; no provider transfer or Release authorized.',
            metadata={'tenant_id': tenant_id, 'operation': 'successor_reference'},
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/native-dry-run')
@permission_required('tenant.manage')
@permission_required('integrations.manage')
def dry_run_native_release_handoff_route(tenant_id: str):
    try:
        _csrf()
        if request.form.get('confirm_native_handoff_dry_run') != 'approved':
            raise ValueError('Explicit Native provider dry-run approval is required.')
        result = dry_run_native_release_handoff_committed(
            tenant_id=tenant_id,
            actor_user_id=int(current_user.id),
            plan_sha256=str(request.form.get('plan_sha256') or ''),
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_native_handoff_dry_run_blocked',
            status='warning',
            title='Native Handoff Dry-Run Blocked',
            message=str(exc),
            detail='No Kubernetes ownership markers or resource specifications were changed.',
            metadata={'tenant_id': tenant_id, 'operation': 'native_handoff_dry_run'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_native_handoff_dry_run_recorded',
            status='success' if result['status'] == 'dry_run_passed' else 'warning',
            title='Native Handoff Preview Recorded',
            message=(
                f"{len(result['previewed_components'])} of "
                f"{result['expected_component_count']} provider previews completed."
            ),
            detail='This was a Kubernetes server-side dry-run only. Release remains blocked.',
            metadata={'tenant_id': tenant_id, 'operation': 'native_handoff_dry_run'},
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/native-readback')
@permission_required('tenant.manage')
@permission_required('integrations.manage')
def inspect_native_external_handoff_route(tenant_id: str):
    """Explicit provider read-back after external owner actions, no Release."""
    try:
        _csrf()
        if request.form.get('confirm_native_handoff_readback') != 'inspect':
            raise ValueError('Explicit provider read-back confirmation is required.')
        result = observe_external_native_handoff_committed(
            tenant_id=tenant_id, actor_user_id=int(current_user.id),
            plan_sha256=str(request.form.get('plan_sha256') or ''),
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_native_handoff_readback_blocked',
            status='warning', title='Native External Handoff Read-Back Blocked',
            message=str(exc), detail='Governance remains Ready and provider resources are untouched.',
            metadata={'tenant_id': tenant_id, 'operation': 'native_external_handoff_readback'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_native_handoff_readback_observed',
            status='info', title='Native Provider Handoff Observed',
            message=f"{result['observed_count']} provider components retained.",
            detail='External successor consent remains unverified. Release remains blocked.',
            metadata={'tenant_id': tenant_id, 'operation': 'native_external_handoff_readback'},
        )
    return _tenant_section_redirect('registry')


@tenant_bp.post('/tenants/<string:tenant_id>/release-governance')
@permission_required('tenant.manage')
@permission_required('integrations.manage')
def release_tenant_governance_route(tenant_id: str):
    try:
        _csrf()
        if request.form.get('confirm_release_governance') != 'approved':
            raise ValueError('Explicit provider-preserving governance Release approval is required.')
        result = release_adopted_tenant_committed(
            tenant_id=tenant_id,
            actor_user_id=int(current_user.id),
            approved=True,
        )
    except (ApiException, ValueError) as exc:
        _record(
            event_type='kubernetes_tenant_release_governance_blocked',
            status='warning',
            title='Release Governance Blocked',
            message=str(exc),
            detail='Existing Kubernetes Namespace/Capsule resources were not deleted or changed.',
            metadata={'tenant_id': tenant_id, 'operation': 'release_tenant_governance'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_release_governance_completed',
            status='success',
            title='Tenant Governance Released',
            message=f"Generation {result['generation']} released; {result['released_namespace_count']} namespaces retained.",
            detail='Provider resources remain externally managed. Re-adopt requires fresh provider discovery.',
            metadata={'tenant_id': tenant_id, 'operation': 'release_tenant_governance'},
        )
    return _tenant_section_redirect('registry')


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


create_group_route = _routes_access.create_group_route
edit_tenant_group_route = _routes_access.edit_tenant_group_route
retire_tenant_group_route = _routes_access.retire_tenant_group_route
reactivate_tenant_group_route = _routes_access.reactivate_tenant_group_route
add_user_membership_route = _routes_access.add_user_membership_route
add_group_membership_route = _routes_access.add_group_membership_route
reactivate_membership_route = _routes_access.reactivate_membership_route
revoke_membership_route = _routes_access.revoke_membership_route
create_access_grant_route = _routes_access.create_access_grant_route
inspect_access_grant_route = _routes_access.inspect_access_grant_route
reconcile_access_grant_route = _routes_access.reconcile_access_grant_route
revoke_access_grant_route = _routes_access.revoke_access_grant_route
create_human_credential_route = _routes_credentials.create_human_credential_route
create_deployer_credential_route = _routes_credentials.create_deployer_credential_route
_credential_feedback = _routes_credentials._credential_feedback
generate_credential_material_route = _routes_credentials.generate_credential_material_route
renew_credential_route = _routes_credentials.renew_credential_route
suspend_credential_route = _routes_credentials.suspend_credential_route
resume_credential_route = _routes_credentials.resume_credential_route
revoke_credential_route = _routes_credentials.revoke_credential_route

_routes_access.register_access_routes()
_routes_credentials.register_credential_routes()
