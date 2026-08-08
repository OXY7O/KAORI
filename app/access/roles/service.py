from __future__ import annotations

from app.extensions.db import db
from app.models import Role, User
from app.rbac.service import normalize_role_slug, replace_role_permissions, role_slug_exists
from app.users.service import record_admin_event


class RoleInputError(ValueError):
    """Validation error raised by the Access role mutation boundary."""


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
    if len(slug) < 2:
        raise RoleInputError('Role slug must contain at least two letters or numbers.')
    if role_slug_exists(slug):
        raise RoleInputError('A role with this slug already exists.')

    role = Role()
    role.name = slug
    role.display_name = (display_name or slug.replace('_', ' ').title()).strip()
    role.description = (description or '').strip() or None
    role.is_system = False
    role.is_active = bool(is_active)
    db.session.add(role)
    db.session.flush()
    effective_permission_ids = replace_role_permissions(role, selected_permission_ids)
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
