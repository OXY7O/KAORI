from __future__ import annotations

from datetime import UTC

from app.access.rbac.policy import (
    actor_delegable_permission_keys,
    is_local_break_glass,
    permission_keys_are_delegable_by_actor,
    role_is_delegable_by_actor,
    role_is_mutation_protected,
    role_slug_is_reserved,
)
from app.access.rbac.service import (
    expand_permission_ids,
    get_role_delete_blockers,
    normalize_role_slug,
    replace_role_permissions,
    role_slug_exists,
)
from app.common.admin_audit import record_admin_event
from app.extensions.db import db
from app.models import Permission, Role, User


class RoleInputError(ValueError):
    """Validation error raised by the Access role mutation boundary."""


class RoleDelegationError(RoleInputError):
    """Raised when a role mutation exceeds the actor's effective permission ceiling."""


class RoleImpactAcknowledgementRequired(RoleInputError):
    """Raised when role deactivation would affect referenced access without acknowledgement."""


def role_version_token(role: Role) -> str:
    updated_at = role.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    permission_ids = ','.join(str(permission.id) for permission in sorted(role.permissions, key=lambda item: item.id))
    return f'{updated_at.astimezone(UTC).isoformat(timespec="microseconds")}|{permission_ids}'


def lock_role_for_mutation(role_id: int) -> Role | None:
    role = db.session.query(Role).populate_existing().filter(Role.id == int(role_id)).with_for_update().one_or_none()
    if role is not None:
        db.session.expire(role, ['permissions'])
    return role


def role_version_matches(role: Role, version_token: str | None) -> bool:
    return bool(version_token and version_token == role_version_token(role))


def delegable_permission_ids(actor: User) -> set[int] | None:
    delegable_keys = actor_delegable_permission_keys(actor)
    if delegable_keys is None:
        return None
    if not delegable_keys:
        return set()
    return {permission.id for permission in Permission.query.filter(Permission.key.in_(delegable_keys)).all()}


def ensure_permission_selection_within_delegation_boundary(
    *,
    actor: User,
    selected_permission_ids: set[int],
) -> set[int]:
    effective_ids = expand_permission_ids(selected_permission_ids)
    if is_local_break_glass(actor):
        return effective_ids

    selected_permissions = Permission.query.filter(Permission.id.in_(effective_ids)).all() if effective_ids else []
    selected_keys = {permission.key for permission in selected_permissions}
    if permission_keys_are_delegable_by_actor(actor, selected_keys):
        return effective_ids

    delegable = actor_delegable_permission_keys(actor) or set()
    blocked = sorted(selected_keys - delegable)
    if not blocked:
        blocked = sorted(selected_keys)
        raise RoleDelegationError(
            'Access-administration permissions can only be delegated by a Local Database Super Admin: '
            + ', '.join(blocked)
            + '.'
        )
    raise RoleDelegationError('Role permission scope exceeds your delegation ceiling: ' + ', '.join(blocked) + '.')


def ensure_role_within_delegation_boundary(*, actor: User, role: Role) -> None:
    if role_is_delegable_by_actor(actor, role):
        return
    raise RoleDelegationError(
        'This role is outside your delegation boundary. Access-administration roles require a Local Database Super Admin; '
        'other roles require an equal or narrower effective permission ceiling.'
    )


def validate_custom_role_slug(slug: str, *, exclude_role_id: int | None = None) -> None:
    if len(slug) < 2:
        raise RoleInputError('Role slug must contain at least two letters or numbers.')
    if role_slug_is_reserved(slug):
        raise RoleInputError('This role slug is reserved by a protected default role definition.')
    if role_slug_exists(slug, exclude_role_id=exclude_role_id):
        raise RoleInputError('A role with this slug already exists.')


def create_custom_role(
    *,
    actor: User,
    name: str | None,
    display_name: str | None,
    description: str | None,
    is_active: bool,
    selected_permission_ids: set[int],
    clone_source: Role | None = None,
) -> Role:
    slug = normalize_role_slug(name)
    validate_custom_role_slug(slug)
    effective_permission_ids = ensure_permission_selection_within_delegation_boundary(
        actor=actor,
        selected_permission_ids=selected_permission_ids,
    )

    role = Role()
    role.name = slug
    role.display_name = (display_name or slug.replace('_', ' ').title()).strip()
    role.description = (description or '').strip() or None
    role.is_system = False
    role.is_active = bool(is_active)
    db.session.add(role)
    db.session.flush()
    effective_permission_ids = replace_role_permissions(role, effective_permission_ids)
    record_admin_event(
        actor=actor,
        action='role.cloned' if clone_source else 'role.created',
        target=role,
        summary=(
            f'Cloned system role {clone_source.display_name} as {role.display_name}.'
            if clone_source
            else f'Created role {role.display_name}.'
        ),
        metadata={
            'role_slug': role.name,
            'source_role_id': clone_source.id if clone_source else None,
            'source_role_slug': clone_source.name if clone_source else None,
            'permission_count': len(effective_permission_ids),
        },
    )
    db.session.commit()
    return role


def update_custom_role(
    *,
    actor: User,
    role: Role,
    name: str | None,
    display_name: str | None,
    description: str | None,
    is_active: bool,
    selected_permission_ids: set[int],
    impact_acknowledged: bool,
) -> set[int]:
    if role_is_mutation_protected(role):
        raise RoleInputError('Source-controlled or system-owned roles cannot be edited from the Access workspace.')
    ensure_role_within_delegation_boundary(actor=actor, role=role)

    slug = normalize_role_slug(name)
    validate_custom_role_slug(slug, exclude_role_id=role.id)
    effective_permission_ids = ensure_permission_selection_within_delegation_boundary(
        actor=actor,
        selected_permission_ids=selected_permission_ids,
    )

    blockers = get_role_delete_blockers(role)
    deactivation_has_impact = bool(
        role.is_active and not bool(is_active) and (blockers['assigned_users'] or blockers['identity_providers'])
    )
    if deactivation_has_impact and not impact_acknowledged:
        raise RoleImpactAcknowledgementRequired(
            'Confirm the user and Identity Provider impact before deactivating this referenced role.'
        )

    role.name = slug
    role.display_name = (display_name or role.display_name).strip()
    role.description = (description or '').strip() or None
    role.is_active = bool(is_active)
    effective_permission_ids = replace_role_permissions(role, effective_permission_ids)
    record_admin_event(
        actor=actor,
        action='role.updated',
        target=role,
        summary=f'Updated role {role.display_name}.',
        metadata={
            'role_slug': role.name,
            'permission_count': len(effective_permission_ids),
            'is_active': role.is_active,
            'deactivation_impact_acknowledged': bool(deactivation_has_impact),
        },
    )
    db.session.commit()
    return effective_permission_ids
