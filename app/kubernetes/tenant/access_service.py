from __future__ import annotations

import re

import yaml
from kubernetes.client.rest import ApiException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.access import (
    ACCESS_PROFILE_CATALOG,
    LATEST_ACCESS_PROFILE_VERSION,
    capsule_cluster_role_manifest,
    TenantAccessScope,
    get_access_profile,
    validate_grant_scope,
)
from app.kubernetes.tenant.access_provider import inspect_provider_access_grant, reconcile_provider_access_grant
from app.kubernetes.tenant.credential_service import revoke_credentials_for_access_grant
from app.models import AuditEvent, User
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantAccessGrantStatus,
    TenantAccessReconciliationStatus,
    TenantEnvironment,
    TenantGroup,
    TenantLifecycleStatus,
    TenantMembership,
    TenantMembershipPrincipalType,
    TenantMembershipStatus,
    TenantNamespace,
)

_GROUP_SLUG_RE = re.compile(r'[^a-z0-9-]+')


class TenantAccessStateConflictError(RuntimeError):
    """Committed Tenant access state changed while a mutation was applying."""


class TenantGroupReconciliationError(RuntimeError):
    """Tenant Group desired identity was committed but dependent RBAC reconciliation needs attention."""


def normalize_group_slug(value: str) -> str:
    slug = _GROUP_SLUG_RE.sub('-', value.strip().lower().replace('_', '-').replace(' ', '-'))
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug or len(slug) > 63:
        raise ValueError('Tenant Group slug must contain 1–63 lowercase letters, numbers, or hyphens.')
    return slug


def _require_ready_tenant(tenant: Tenant) -> None:
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant is not Ready; new access mutations are frozen during decommission.')


def create_tenant_group(*, tenant: Tenant, name: str, subject_name: str | None = None) -> TenantGroup:
    _require_ready_tenant(tenant)
    display_name = name.strip()
    if not display_name or len(display_name) > 120:
        raise ValueError('Tenant Group name is required and must be at most 120 characters.')
    slug = normalize_group_slug(display_name)
    if TenantGroup.query.filter_by(tenant_id=tenant.id, slug=slug).first() is not None:
        raise ValueError('A Tenant Group with this slug already exists in the selected Tenant.')

    group = TenantGroup()
    group.tenant = tenant
    group.name = display_name
    group.slug = slug
    group.subject_name = (subject_name or f'kaori:tenant:{tenant.slug}:group:{slug}').strip()
    if not group.subject_name:
        raise ValueError('Tenant Group requires a Kubernetes group subject identity.')
    group.enabled = True
    db.session.add(group)
    db.session.flush()
    return group


def add_user_membership(*, tenant: Tenant, user: User, subject_name: str | None = None) -> TenantMembership:
    _require_ready_tenant(tenant)
    if not user.is_active:
        raise ValueError('Only an active KAORI user can become a Tenant member.')
    existing = TenantMembership.query.filter_by(tenant_id=tenant.id, user_id=user.id).first()
    if existing is not None:
        if existing.status == TenantMembershipStatus.REVOKED.value:
            raise ValueError(
                'This user already has a revoked Tenant membership. Reactivate it from the Membership Registry.'
            )
        raise ValueError('This user is already an active member of the selected Tenant.')

    membership = TenantMembership()
    membership.tenant = tenant
    membership.principal_type = TenantMembershipPrincipalType.USER.value
    membership.user = user
    membership.subject_name = (subject_name or user.username).strip()
    membership.status = TenantMembershipStatus.ACTIVE.value
    db.session.add(membership)
    db.session.flush()
    return membership


def add_group_membership(*, tenant: Tenant, group: TenantGroup) -> TenantMembership:
    _require_ready_tenant(tenant)
    if group.tenant_id != tenant.id:
        raise ValueError('Tenant Group membership cannot cross Tenant boundaries.')
    if not group.enabled:
        raise ValueError('Only an enabled Tenant Group can become a Tenant member.')
    existing = TenantMembership.query.filter_by(tenant_id=tenant.id, group_id=group.id).first()
    if existing is not None:
        if existing.status == TenantMembershipStatus.REVOKED.value:
            raise ValueError(
                'This Tenant Group already has a revoked membership. Reactivate it from the Membership Registry.'
            )
        raise ValueError('This Tenant Group is already an active member of the selected Tenant.')

    membership = TenantMembership()
    membership.tenant = tenant
    membership.principal_type = TenantMembershipPrincipalType.GROUP.value
    membership.group = group
    membership.subject_name = group.subject_name
    membership.status = TenantMembershipStatus.ACTIVE.value
    db.session.add(membership)
    db.session.flush()
    return membership


def _grant_scope(
    *,
    membership: TenantMembership,
    scope_type: str,
    tenant_environment_id: int | None,
    tenant_namespace_id: int | None,
) -> tuple[TenantEnvironment | None, TenantNamespace | None]:
    scope = TenantAccessScope(scope_type)
    environment = (
        db.session.get(TenantEnvironment, tenant_environment_id) if tenant_environment_id is not None else None
    )
    namespace = db.session.get(TenantNamespace, tenant_namespace_id) if tenant_namespace_id is not None else None

    if scope is TenantAccessScope.TENANT:
        if environment is not None or namespace is not None:
            raise ValueError('Tenant scope cannot include environment or namespace references.')
    elif scope is TenantAccessScope.ENVIRONMENT:
        if environment is None or namespace is not None:
            raise ValueError('Environment scope requires exactly one Tenant environment.')
        if environment.tenant_id != membership.tenant_id:
            raise ValueError('Environment scope cannot cross Tenant boundaries.')
    else:
        if namespace is None or environment is not None:
            raise ValueError('Namespace scope requires exactly one managed Tenant namespace.')
        if namespace.environment.tenant_id != membership.tenant_id:
            raise ValueError('Namespace scope cannot cross Tenant boundaries.')
    return environment, namespace


def _record_grant_event(
    *,
    actor: User | None,
    grant: TenantAccessGrant,
    action: str,
    summary: str,
    outcome: str,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_access_grant'
    event.target_id = grant.public_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': grant.tenant_id,
        'membership_id': grant.membership_id,
        'scope_type': grant.scope_type,
        'access_profile': grant.access_profile,
        'access_profile_version': grant.access_profile_version,
        'grant_status': grant.status,
        'reconciliation_status': grant.reconciliation_status,
        'outcome': outcome,
        'correlation_id': grant.correlation_id,
    }
    db.session.add(event)


def create_access_grant_committed(
    *,
    membership_id: int,
    access_profile: str,
    scope_type: str,
    tenant_environment_id: int | None = None,
    tenant_namespace_id: int | None = None,
    actor: User | None = None,
) -> TenantAccessGrant:
    membership = db.session.get(TenantMembership, membership_id)
    if membership is None or membership.status != TenantMembershipStatus.ACTIVE.value:
        raise ValueError('Select an active Tenant membership.')
    _require_ready_tenant(membership.tenant)
    profile = get_access_profile(access_profile)
    environment, namespace = _grant_scope(
        membership=membership,
        scope_type=scope_type,
        tenant_environment_id=tenant_environment_id,
        tenant_namespace_id=tenant_namespace_id,
    )

    grant = TenantAccessGrant()
    grant.tenant_id = membership.tenant_id
    grant.membership = membership
    grant.environment = environment
    grant.namespace = namespace
    grant.scope_type = TenantAccessScope(scope_type).value
    grant.access_profile = profile.key.value
    grant.access_profile_version = profile.version
    grant.status = TenantAccessGrantStatus.ACTIVE.value
    grant.reconciliation_status = TenantAccessReconciliationStatus.PENDING.value
    validate_grant_scope(grant)
    db.session.add(grant)

    try:
        db.session.flush()
        reconcile_provider_access_grant(grant)
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.created',
            summary=(
                'Tenant Access Grant was committed and verified.'
                if grant.reconciliation_status == TenantAccessReconciliationStatus.READY.value
                else 'Tenant Access Grant was committed; effective provider reconciliation is still pending.'
            ),
            outcome='success' if grant.reconciliation_status == TenantAccessReconciliationStatus.READY.value else 'warning',
        )
        db.session.commit()
        return grant
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAccessStateConflictError(
            'Committed Tenant access state changed while this grant was being applied. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        if grant.id is not None:
            _record_grant_event(
                actor=actor,
                grant=grant,
                action='tenant_access_grant.reconcile_failed',
                summary='Tenant Access Grant was committed but provider reconciliation failed.',
                outcome='failed',
            )
            db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def revoke_access_grant_committed(*, grant_id: int, actor: User | None = None) -> TenantAccessGrant:
    grant = db.session.get(TenantAccessGrant, grant_id)
    if grant is None:
        raise ValueError('Selected Tenant Access Grant no longer exists.')

    grant.status = TenantAccessGrantStatus.REVOKED.value
    try:
        revoke_credentials_for_access_grant(grant, actor=actor)
        reconcile_provider_access_grant(grant)
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.revoked',
            summary=(
                'Tenant Access Grant and dependent credential access were removed from Kubernetes.'
                if grant.reconciliation_status == TenantAccessReconciliationStatus.REVOKED.value
                else 'Tenant Access Grant is revoked in KAORI, but effective cleanup remains unverified.'
            ),
            outcome='success' if grant.reconciliation_status == TenantAccessReconciliationStatus.REVOKED.value else 'warning',
        )
        db.session.commit()
        return grant
    except (ApiException, ValueError):
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.revoke_failed',
            summary='Tenant Access Grant is revoked in KAORI but provider access removal requires attention.',
            outcome='failed',
        )
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def create_tenant_group_committed(*, tenant: Tenant, name: str, subject_name: str | None = None) -> TenantGroup:
    try:
        group = create_tenant_group(tenant=tenant, name=name, subject_name=subject_name)
        db.session.commit()
        return group
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAccessStateConflictError(
            'Committed Tenant Group state changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _record_group_event(
    *,
    actor: User | None,
    group: TenantGroup,
    action: str,
    summary: str,
    outcome: str,
    previous_name: str | None = None,
    previous_subject_name: str | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_group'
    event.target_id = group.public_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': group.tenant_id,
        'group_name': group.name,
        'group_slug': group.slug,
        'subject_name': group.subject_name,
        'enabled': group.enabled,
        'previous_name': previous_name,
        'previous_subject_name': previous_subject_name,
        'outcome': outcome,
        'correlation_id': group.correlation_id,
    }
    db.session.add(event)


def update_tenant_group_committed(
    *,
    group_id: int,
    name: str,
    subject_name: str,
    actor: User | None = None,
) -> TenantGroup:
    group = db.session.get(TenantGroup, group_id)
    if group is None:
        raise ValueError('Selected Tenant Group no longer exists.')
    _require_ready_tenant(group.tenant)

    display_name = name.strip()
    subject = subject_name.strip()
    if not display_name or len(display_name) > 120:
        raise ValueError('Tenant Group name is required and must be at most 120 characters.')
    if not subject or len(subject) > 253:
        raise ValueError('Kubernetes Group Subject is required and must be at most 253 characters.')

    duplicate_subject = TenantGroup.query.filter(
        TenantGroup.tenant_id == group.tenant_id,
        TenantGroup.id != group.id,
        TenantGroup.subject_name == subject,
    ).first()
    if duplicate_subject is not None:
        raise ValueError('Another Tenant Group already uses this Kubernetes Group Subject in the selected Tenant.')

    previous_name = group.name
    previous_subject = group.subject_name
    subject_changed = subject != previous_subject

    group.name = display_name
    group.subject_name = subject
    if subject_changed:
        for membership in group.memberships:
            membership.subject_name = subject

    _record_group_event(
        actor=actor,
        group=group,
        action='tenant_group.updated',
        summary=(
            'Tenant Group display metadata and Kubernetes Group Subject were updated.'
            if subject_changed
            else 'Tenant Group display name was updated.'
        ),
        outcome='success',
        previous_name=previous_name,
        previous_subject_name=previous_subject,
    )
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAccessStateConflictError(
            'Committed Tenant Group identity changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise

    if not subject_changed:
        return group

    reconciliation_errors: list[str] = []
    active_grants = [
        grant
        for membership in group.memberships
        if membership.status == TenantMembershipStatus.ACTIVE.value
        for grant in membership.access_grants
        if grant.status == TenantAccessGrantStatus.ACTIVE.value
    ]
    for grant in sorted(active_grants, key=lambda item: item.id or 0):
        try:
            reconcile_access_grant_committed(grant_id=int(grant.id), actor=actor)
        except (ApiException, ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            reconciliation_errors.append(str(exc))

    if reconciliation_errors:
        raise TenantGroupReconciliationError(
            'Tenant Group subject was updated, but one or more active Access Grants require Reconcile.'
        )
    return group


def retire_tenant_group_committed(*, group_id: int, actor: User | None = None) -> TenantGroup:
    group = db.session.get(TenantGroup, group_id)
    if group is None:
        raise ValueError('Selected Tenant Group no longer exists.')
    if not group.enabled:
        return group
    _require_ready_tenant(group.tenant)

    active_memberships = [
        membership for membership in group.memberships if membership.status == TenantMembershipStatus.ACTIVE.value
    ]
    if active_memberships:
        raise ValueError('Revoke the active Tenant Group membership before retiring this group.')

    unresolved_grants = [
        grant
        for membership in group.memberships
        for grant in membership.access_grants
        if grant.status != TenantAccessGrantStatus.REVOKED.value
        or grant.reconciliation_status != TenantAccessReconciliationStatus.REVOKED.value
    ]
    if unresolved_grants:
        raise ValueError('Resolve provider cleanup for previous Access Grants before retiring this Tenant Group.')

    group.enabled = False
    _record_group_event(
        actor=actor,
        group=group,
        action='tenant_group.retired',
        summary='Tenant Group was retired while its historical membership and grant evidence were retained.',
        outcome='success',
    )
    try:
        db.session.commit()
        return group
    except SQLAlchemyError:
        db.session.rollback()
        raise


def reactivate_tenant_group_committed(*, group_id: int, actor: User | None = None) -> TenantGroup:
    group = db.session.get(TenantGroup, group_id)
    if group is None:
        raise ValueError('Selected Tenant Group no longer exists.')
    if group.enabled:
        return group
    _require_ready_tenant(group.tenant)

    group.enabled = True
    _record_group_event(
        actor=actor,
        group=group,
        action='tenant_group.reactivated',
        summary='Tenant Group was reactivated for future Tenant Membership use.',
        outcome='success',
    )
    try:
        db.session.commit()
        return group
    except SQLAlchemyError:
        db.session.rollback()
        raise


def add_user_membership_committed(
    *,
    tenant: Tenant,
    user: User,
    subject_name: str | None = None,
) -> TenantMembership:
    try:
        membership = add_user_membership(tenant=tenant, user=user, subject_name=subject_name)
        db.session.commit()
        return membership
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAccessStateConflictError(
            'Committed Tenant membership state changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def add_group_membership_committed(*, tenant: Tenant, group: TenantGroup) -> TenantMembership:
    try:
        membership = add_group_membership(tenant=tenant, group=group)
        db.session.commit()
        return membership
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAccessStateConflictError(
            'Committed Tenant membership state changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _actor_by_id(actor_user_id: int | None) -> User | None:
    if actor_user_id is None:
        return None
    actor = db.session.get(User, actor_user_id)
    if actor is None:
        raise ValueError('Authenticated KAORI user no longer exists.')
    return actor


def create_tenant_group_by_id_committed(
    *,
    tenant_id: str,
    name: str,
    subject_name: str | None = None,
) -> TenantGroup:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Select a Tenant.')
    return create_tenant_group_committed(tenant=tenant, name=name, subject_name=subject_name)


def update_tenant_group_by_id_committed(
    *,
    group_id: int,
    name: str,
    subject_name: str,
    actor_user_id: int | None = None,
) -> TenantGroup:
    return update_tenant_group_committed(
        group_id=group_id,
        name=name,
        subject_name=subject_name,
        actor=_actor_by_id(actor_user_id),
    )


def retire_tenant_group_by_id_committed(
    *,
    group_id: int,
    actor_user_id: int | None = None,
) -> TenantGroup:
    return retire_tenant_group_committed(group_id=group_id, actor=_actor_by_id(actor_user_id))


def reactivate_tenant_group_by_id_committed(
    *,
    group_id: int,
    actor_user_id: int | None = None,
) -> TenantGroup:
    return reactivate_tenant_group_committed(group_id=group_id, actor=_actor_by_id(actor_user_id))


def add_user_membership_by_id_committed(
    *,
    tenant_id: str,
    user_id: int,
    subject_name: str | None = None,
) -> TenantMembership:
    tenant = db.session.get(Tenant, tenant_id)
    user = db.session.get(User, user_id)
    if tenant is None or user is None:
        raise ValueError('Select a valid Tenant and active user.')
    return add_user_membership_committed(tenant=tenant, user=user, subject_name=subject_name)


def add_group_membership_by_id_committed(*, tenant_id: str, group_id: int) -> TenantMembership:
    tenant = db.session.get(Tenant, tenant_id)
    group = db.session.get(TenantGroup, group_id)
    if tenant is None or group is None:
        raise ValueError('Select a valid Tenant and Tenant Group.')
    return add_group_membership_committed(tenant=tenant, group=group)


def create_access_grant_by_id_committed(
    *,
    membership_id: int,
    access_profile: str,
    scope_type: str,
    tenant_environment_id: int | None = None,
    tenant_namespace_id: int | None = None,
    actor_user_id: int | None = None,
) -> TenantAccessGrant:
    return create_access_grant_committed(
        membership_id=membership_id,
        access_profile=access_profile,
        scope_type=scope_type,
        tenant_environment_id=tenant_environment_id,
        tenant_namespace_id=tenant_namespace_id,
        actor=_actor_by_id(actor_user_id),
    )


def inspect_access_grant_by_id_committed(
    *,
    grant_id: int,
    actor_user_id: int | None = None,
) -> TenantAccessGrant:
    return inspect_access_grant_committed(grant_id=grant_id, actor=_actor_by_id(actor_user_id))


def reconcile_access_grant_by_id_committed(
    *,
    grant_id: int,
    actor_user_id: int | None = None,
) -> TenantAccessGrant:
    return reconcile_access_grant_committed(grant_id=grant_id, actor=_actor_by_id(actor_user_id))


def revoke_access_grant_by_id_committed(
    *,
    grant_id: int,
    actor_user_id: int | None = None,
) -> TenantAccessGrant:
    return revoke_access_grant_committed(grant_id=grant_id, actor=_actor_by_id(actor_user_id))


def revoke_membership_by_id_committed(
    *,
    membership_id: int,
    actor_user_id: int | None = None,
) -> TenantMembership:
    return revoke_membership_committed(membership_id=membership_id, actor=_actor_by_id(actor_user_id))


def reactivate_membership_by_id_committed(
    *,
    membership_id: int,
    actor_user_id: int | None = None,
) -> TenantMembership:
    return reactivate_membership_committed(membership_id=membership_id, actor=_actor_by_id(actor_user_id))


def _record_membership_event(
    *,
    actor: User | None,
    membership: TenantMembership,
    action: str,
    summary: str,
    outcome: str,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_membership'
    event.target_id = str(membership.id)
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': membership.tenant_id,
        'principal_type': membership.principal_type,
        'subject_name': membership.subject_name,
        'membership_status': membership.status,
        'outcome': outcome,
        'correlation_id': membership.correlation_id,
    }
    db.session.add(event)


def revoke_membership_committed(*, membership_id: int, actor: User | None = None) -> TenantMembership:
    membership = db.session.get(TenantMembership, membership_id)
    if membership is None:
        raise ValueError('Selected Tenant membership no longer exists.')
    if membership.status == TenantMembershipStatus.REVOKED.value:
        return membership

    membership.status = TenantMembershipStatus.REVOKED.value
    errors: list[str] = []
    for grant in sorted(membership.access_grants, key=lambda item: item.id or 0):
        if grant.status == TenantAccessGrantStatus.REVOKED.value:
            continue
        grant.status = TenantAccessGrantStatus.REVOKED.value
        try:
            reconcile_provider_access_grant(grant)
        except (ApiException, ValueError) as exc:
            errors.append(str(exc))
            _record_grant_event(
                actor=actor,
                grant=grant,
                action='tenant_access_grant.membership_revoke_failed',
                summary='Tenant Access Grant was revoked in KAORI but provider cleanup requires attention.',
                outcome='failed',
            )
        else:
            if grant.reconciliation_status != TenantAccessReconciliationStatus.REVOKED.value:
                errors.append(f'Grant {grant.public_id}: effective provider cleanup is unverified.')
            _record_grant_event(
                actor=actor,
                grant=grant,
                action='tenant_access_grant.membership_revoked',
                summary='Tenant Access Grant was revoked because its membership was revoked.',
                outcome=(
                    'success' if grant.reconciliation_status == TenantAccessReconciliationStatus.REVOKED.value
                    else 'warning'
                ),
            )

    _record_membership_event(
        actor=actor,
        membership=membership,
        action='tenant_membership.revoked',
        summary='Tenant membership was revoked and dependent Access Grants were disabled.',
        outcome='warning' if errors else 'success',
    )
    db.session.commit()
    if errors:
        raise ValueError(
            'Tenant membership is revoked in KAORI, but one or more Kubernetes RoleBindings require operator attention.'
        )
    return membership


def reactivate_membership_committed(*, membership_id: int, actor: User | None = None) -> TenantMembership:
    membership = db.session.get(TenantMembership, membership_id)
    if membership is None:
        raise ValueError('Selected Tenant membership no longer exists.')
    if membership.status == TenantMembershipStatus.ACTIVE.value:
        return membership

    _require_ready_tenant(membership.tenant)
    if membership.principal_type == TenantMembershipPrincipalType.USER.value:
        if membership.user is None or not membership.user.is_active:
            raise ValueError('The linked KAORI user is not active; reactivate the user before Tenant membership.')
    elif membership.principal_type == TenantMembershipPrincipalType.GROUP.value:
        if membership.group is None or not membership.group.enabled:
            raise ValueError('The linked Tenant Group is disabled; enable the group before membership reactivation.')
    else:
        raise ValueError('Membership reactivation currently supports User and Tenant Group principals only.')

    unresolved_grants = [
        grant
        for grant in membership.access_grants
        if grant.status != TenantAccessGrantStatus.REVOKED.value
        or grant.reconciliation_status != TenantAccessReconciliationStatus.REVOKED.value
    ]
    if unresolved_grants:
        raise ValueError('Resolve provider cleanup for all previous Access Grants before reactivating this membership.')

    membership.status = TenantMembershipStatus.ACTIVE.value
    _record_membership_event(
        actor=actor,
        membership=membership,
        action='tenant_membership.reactivated',
        summary='Tenant membership was reactivated; previous Access Grants remain revoked.',
        outcome='success',
    )
    try:
        db.session.commit()
        return membership
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAccessStateConflictError(
            'Committed Tenant membership state changed during reactivation. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def reconcile_access_grants_for_namespace_committed(
    *,
    namespace: TenantNamespace,
    actor: User | None = None,
) -> dict[str, int]:
    """Expand active Environment/Tenant grants after explicit namespace provisioning.

    This is an operation follow-up, not an inventory/sync mutation path. Namespace
    scope remains explicit and is never inferred automatically.
    """

    tenant = namespace.environment.tenant
    if tenant.provider_key != tenant.reconciliation_authority or tenant.provider_key not in {
        'native_kubernetes', 'capsule'
    }:
        return {'matched': 0, 'reconciled': 0, 'failed': 0}

    grants = (
        TenantAccessGrant.query.filter(
            TenantAccessGrant.tenant_id == tenant.id,
            TenantAccessGrant.status == TenantAccessGrantStatus.ACTIVE.value,
            (
                (TenantAccessGrant.scope_type == TenantAccessScope.TENANT.value)
                | (
                    (TenantAccessGrant.scope_type == TenantAccessScope.ENVIRONMENT.value)
                    & (TenantAccessGrant.tenant_environment_id == namespace.tenant_environment_id)
                )
            ),
        )
        .order_by(TenantAccessGrant.id.asc())
        .all()
    )

    reconciled = 0
    failed = 0
    for grant in grants:
        try:
            reconcile_provider_access_grant(grant)
            _record_grant_event(
                actor=actor,
                grant=grant,
                action='tenant_access_grant.namespace_scope_expanded',
                summary=(
                    f'Tenant Access Grant reconciled after namespace {namespace.namespace} entered its committed scope.'
                ),
                outcome='success',
            )
            db.session.commit()
            reconciled += 1
        except (ApiException, ValueError):
            if grant.id is not None:
                _record_grant_event(
                    actor=actor,
                    grant=grant,
                    action='tenant_access_grant.namespace_scope_expand_failed',
                    summary=(
                        f'Namespace {namespace.namespace} entered the committed scope, '
                        'but Access Grant reconciliation requires operator attention.'
                    ),
                    outcome='failed',
                )
                db.session.commit()
            failed += 1
        except SQLAlchemyError:
            db.session.rollback()
            failed += 1

    return {'matched': len(grants), 'reconciled': reconciled, 'failed': failed}


def inspect_access_grant_committed(*, grant_id: int, actor: User | None = None) -> TenantAccessGrant:
    grant = db.session.get(TenantAccessGrant, grant_id)
    if grant is None:
        raise ValueError('Selected Tenant Access Grant no longer exists.')
    try:
        inspect_provider_access_grant(grant)
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.inspected',
            summary='Tenant Access Grant effective Kubernetes RBAC was inspected.',
            outcome='success',
        )
        db.session.commit()
        return grant
    except (ApiException, ValueError):
        db.session.rollback()
        raise


def reconcile_access_grant_committed(*, grant_id: int, actor: User | None = None) -> TenantAccessGrant:
    grant = db.session.get(TenantAccessGrant, grant_id)
    if grant is None:
        raise ValueError('Selected Tenant Access Grant no longer exists.')
    _require_ready_tenant(grant.tenant)
    try:
        reconcile_provider_access_grant(grant)
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.reconciled',
            summary='Tenant Access Grant provider reconciliation was attempted; effective state was read back.',
            outcome='success' if grant.reconciliation_status in {'ready', 'revoked'} else 'warning',
        )
        db.session.commit()
        return grant
    except (ApiException, ValueError):
        if grant.id is not None:
            _record_grant_event(
                actor=actor,
                grant=grant,
                action='tenant_access_grant.reconcile_failed',
                summary='Tenant Access Grant reconciliation requires operator attention.',
                outcome='failed',
            )
            db.session.commit()
        raise


def get_tenant_access_context() -> dict[str, object]:
    tenant_options = (
        Tenant.query.filter(Tenant.lifecycle_status == TenantLifecycleStatus.READY.value)
        .order_by(Tenant.name.asc())
        .all()
    )
    user_options = (
        User.query.filter(User.account_is_active.is_(True), User.deleted_at.is_(None))
        .order_by(User.username.asc())
        .all()
    )
    group_options = (
        TenantGroup.query.join(Tenant, Tenant.id == TenantGroup.tenant_id)
        .filter(
            TenantGroup.enabled.is_(True),
            Tenant.lifecycle_status == TenantLifecycleStatus.READY.value,
        )
        .order_by(TenantGroup.name.asc())
        .all()
    )
    membership_options = (
        TenantMembership.query.join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .filter(
            TenantMembership.status == TenantMembershipStatus.ACTIVE.value,
            Tenant.lifecycle_status == TenantLifecycleStatus.READY.value,
        )
        .order_by(TenantMembership.created_at.desc())
        .all()
    )
    environment_options = (
        TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(Tenant.lifecycle_status == TenantLifecycleStatus.READY.value)
        .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
        .all()
    )
    namespace_options = (
        TenantNamespace.query.join(TenantEnvironment, TenantEnvironment.id == TenantNamespace.tenant_environment_id)
        .join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(
            Tenant.lifecycle_status == TenantLifecycleStatus.READY.value,
            TenantNamespace.provisioning_status == 'ready',
        )
        .order_by(Tenant.name.asc(), TenantNamespace.namespace.asc())
        .all()
    )
    profile_order = ('viewer', 'operator', 'tenant_admin', 'deployer')
    profiles = [
        ACCESS_PROFILE_CATALOG[(key, LATEST_ACCESS_PROFILE_VERSION[key])]
        for key in profile_order
        if key in LATEST_ACCESS_PROFILE_VERSION
    ]
    capsule_role_documents = [capsule_cluster_role_manifest(profile) for profile in profiles]
    capsule_role_manifests = [
        {
            'label': profile.label,
            'version': profile.version,
            'name': document['metadata']['name'],
            'yaml': yaml.safe_dump(document, sort_keys=False, explicit_start=True),
        }
        for profile, document in zip(profiles, capsule_role_documents, strict=True)
    ]
    return {
        'access_tenant_options': tenant_options,
        'access_user_options': user_options,
        'access_group_options': group_options,
        'access_membership_options': membership_options,
        'access_environment_options': environment_options,
        'access_namespace_options': namespace_options,
        'access_profiles': profiles,
        'access_capsule_role_manifests': capsule_role_manifests,
        'access_capsule_role_bundle_yaml': yaml.safe_dump_all(
            capsule_role_documents, sort_keys=False, explicit_start=True
        ),
        'recent_tenant_groups': TenantGroup.query.order_by(TenantGroup.created_at.desc()).limit(5).all(),
        'recent_tenant_memberships': TenantMembership.query.order_by(TenantMembership.created_at.desc()).limit(5).all(),
        'recent_access_grants': TenantAccessGrant.query.order_by(TenantAccessGrant.created_at.desc()).limit(5).all(),
        'external_capsule_tenants': [
            tenant for tenant in tenant_options
            if tenant.provider_key == 'capsule' and tenant.provider_state == 'capsule'
        ],
        'recent_external_capsule_access': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_external_access_inventory')
            .order_by(AuditEvent.id.desc()).limit(5).all()
        ),
        'recent_capsule_access_drift': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_access_drift_evidence')
            .order_by(AuditEvent.id.desc()).limit(5).all()
        ),
    }


def active_membership_count(tenant_id: str) -> int:
    return TenantMembership.query.filter_by(
        tenant_id=tenant_id,
        status=TenantMembershipStatus.ACTIVE.value,
    ).count()


def active_grant_count(tenant_id: str) -> int:
    return TenantAccessGrant.query.filter_by(
        tenant_id=tenant_id,
        status=TenantAccessGrantStatus.ACTIVE.value,
    ).count()


def access_profile_usage(access_profile: str) -> int:
    return TenantAccessGrant.query.filter(
        func.lower(TenantAccessGrant.access_profile) == access_profile.strip().lower(),
        TenantAccessGrant.status == TenantAccessGrantStatus.ACTIVE.value,
    ).count()
