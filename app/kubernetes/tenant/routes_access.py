from __future__ import annotations

from flask import request
from flask_login import current_user
from kubernetes.client.rest import ApiException

from app.access.rbac.decorators import permission_required
from app.kubernetes.tenant.access_service import (
    TenantAccessStateConflictError,
    TenantGroupReconciliationError,
    add_group_membership_by_id_committed,
    add_user_membership_by_id_committed,
    create_access_grant_by_id_committed,
    create_tenant_group_by_id_committed,
    inspect_access_grant_by_id_committed,
    reactivate_membership_by_id_committed,
    reactivate_tenant_group_by_id_committed,
    reconcile_access_grant_by_id_committed,
    retire_tenant_group_by_id_committed,
    revoke_access_grant_by_id_committed,
    revoke_membership_by_id_committed,
    update_tenant_group_by_id_committed,
)
from app.kubernetes.tenant.route_common import (
    _csrf,
    _optional_int,
    _record,
    _required_int,
    _tenant_section_redirect,
    tenant_bp,
)
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


def register_access_routes() -> None:
    """Import marker for Tenant Access/RBAC route registration."""
