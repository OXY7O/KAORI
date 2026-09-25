from __future__ import annotations

import re

from kubernetes.client.rest import ApiException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.access import TenantAccessScope, get_access_profile, validate_grant_scope
from app.kubernetes.tenant.access_reconciliation import reconcile_native_access_grant
from app.models import AuditEvent, User
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantAccessGrantStatus,
    TenantAccessReconciliationStatus,
    TenantEnvironment,
    TenantGroup,
    TenantMembership,
    TenantMembershipPrincipalType,
    TenantMembershipStatus,
    TenantNamespace,
)

_GROUP_SLUG_RE = re.compile(r'[^a-z0-9-]+')


class TenantAccessStateConflictError(RuntimeError):
    """Committed Tenant access state changed while a mutation was applying."""


def normalize_group_slug(value: str) -> str:
    slug = _GROUP_SLUG_RE.sub('-', value.strip().lower().replace('_', '-').replace(' ', '-'))
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug or len(slug) > 63:
        raise ValueError('Tenant Group slug must contain 1–63 lowercase letters, numbers, or hyphens.')
    return slug


def create_tenant_group(*, tenant: Tenant, name: str, subject_name: str | None = None) -> TenantGroup:
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
    if not user.is_active:
        raise ValueError('Only an active KAORI user can become a Tenant member.')
    if TenantMembership.query.filter_by(tenant_id=tenant.id, user_id=user.id).first() is not None:
        raise ValueError('This user is already a member of the selected Tenant.')

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
    if group.tenant_id != tenant.id:
        raise ValueError('Tenant Group membership cannot cross Tenant boundaries.')
    if not group.enabled:
        raise ValueError('Only an enabled Tenant Group can become a Tenant member.')
    if TenantMembership.query.filter_by(tenant_id=tenant.id, group_id=group.id).first() is not None:
        raise ValueError('This group is already a member of the selected Tenant.')

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
        reconcile_native_access_grant(grant)
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.created',
            summary='Tenant Access Grant was committed and reconciled.',
            outcome='success',
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
        reconcile_native_access_grant(grant)
        _record_grant_event(
            actor=actor,
            grant=grant,
            action='tenant_access_grant.revoked',
            summary='Tenant Access Grant was revoked and effective RoleBinding access was removed.',
            outcome='success',
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
