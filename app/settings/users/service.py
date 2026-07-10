from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_

from app.extensions import db
from app.models import AuditEvent, Role, User

USER_STATUS_OPTIONS = ['all', 'active', 'inactive', 'deleted']
USER_AUTH_SOURCE_OPTIONS = ['all', 'database', 'ldap', 'sso']


def normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or '').strip()
    return normalized or None


def normalize_user_filters(args: Mapping[str, str | None]) -> dict[str, Any]:
    status = (args.get('status') or 'all').strip().lower()
    auth_source = (args.get('auth_source') or 'all').strip().lower()
    role_id_raw = (args.get('role_id') or 'all').strip()

    try:
        page = max(int(args.get('page') or 1), 1)
    except ValueError:
        page = 1

    try:
        per_page = int(args.get('per_page') or 10)
    except ValueError:
        per_page = 10

    if per_page not in [5, 10, 25, 50]:
        per_page = 10

    return {
        'search': (args.get('search') or '').strip(),
        'status': status if status in USER_STATUS_OPTIONS else 'all',
        'auth_source': auth_source if auth_source in USER_AUTH_SOURCE_OPTIONS else 'all',
        'role_id': int(role_id_raw) if role_id_raw.isdigit() else None,
        'page': page,
        'per_page': per_page,
    }


def build_users_payload(filters: dict[str, Any], actor: User | None = None) -> dict[str, Any]:
    query = User.query

    if filters['status'] != 'deleted':
        query = query.filter(User.deleted_at.is_(None))

    if filters['status'] == 'active':
        query = query.filter(User.account_is_active.is_(True), User.deleted_at.is_(None))
    elif filters['status'] == 'inactive':
        query = query.filter(User.account_is_active.is_(False), User.deleted_at.is_(None))
    elif filters['status'] == 'deleted':
        query = query.filter(User.deleted_at.is_not(None))

    if filters['auth_source'] != 'all':
        query = query.filter(User.auth_source == filters['auth_source'])

    if filters['role_id']:
        query = query.filter(User.role_id == filters['role_id'])

    if filters['search']:
        search_term = f"%{filters['search']}%"
        query = query.filter(
            or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term),
                User.display_name.ilike(search_term),
            )
        )

    total_items = query.count()
    total_pages = max((total_items + filters['per_page'] - 1) // filters['per_page'], 1)
    page = min(filters['page'], total_pages)

    users = (
        query.order_by(User.deleted_at.asc(), User.account_is_active.desc(), User.username.asc())
        .offset((page - 1) * filters['per_page'])
        .limit(filters['per_page'])
        .all()
    )

    start_item = ((page - 1) * filters['per_page']) + 1 if total_items else 0
    end_item = min(page * filters['per_page'], total_items) if total_items else 0

    active_users = User.query.filter(User.account_is_active.is_(True), User.deleted_at.is_(None)).count()
    inactive_users = User.query.filter(User.account_is_active.is_(False), User.deleted_at.is_(None)).count()
    external_users = User.query.filter(User.auth_source != 'database', User.deleted_at.is_(None)).count()

    return {
        'users': users,
        'roles': Role.query.filter_by(is_active=True).order_by(Role.display_name.asc()).all(),
        'summary': {
            'total': User.query.filter(User.deleted_at.is_(None)).count(),
            'active': active_users,
            'inactive': inactive_users,
            'external': external_users,
        },
        'filters': {**filters, 'page': page},
        'pagination': {
            'page': page,
            'per_page': filters['per_page'],
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': start_item,
            'end_item': end_item,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': max(page - 1, 1),
            'next_page': min(page + 1, total_pages),
        },
        'per_page_options': [5, 10, 25, 50],
        'status_options': USER_STATUS_OPTIONS,
        'auth_source_options': USER_AUTH_SOURCE_OPTIONS,
        'user_actions': build_user_action_policies(actor, users),
    }


def assign_user_form_choices(form: Any, *, include_admin_roles: bool = True) -> None:
    query = Role.query.filter_by(is_active=True)
    if not include_admin_roles:
        query = query.filter(Role.name != 'admin')

    roles = query.order_by(Role.display_name.asc()).all()
    form.role_id.choices = [(role.id, role.display_name) for role in roles]




def find_active_user_identity_conflict(*, username: str, email: str, exclude_user_id: int | None = None) -> User | None:
    normalized_username = username.strip()
    normalized_email = email.strip().lower()

    query = User.query.filter(
        User.deleted_at.is_(None),
        or_(
            User.username == normalized_username,
            User.email == normalized_email,
        ),
    )

    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    return query.first()

def create_or_update_user(form: Any, user: User | None = None) -> User:
    is_new = user is None
    if user is None:
        user = User()

    user.username = form.username.data.strip()
    user.email = form.email.data.strip().lower()
    user.display_name = normalize_optional_text(form.display_name.data)
    user.auth_source = form.auth_source.data
    user.external_id = normalize_optional_text(form.external_id.data)
    user.role_id = form.role_id.data
    role = db.session.get(Role, form.role_id.data)
    if role:
        user.role = role.name
    user.account_is_active = bool(form.is_active.data)
    user.is_super_admin = bool(form.is_super_admin.data)

    # Password assignment is only handled during user creation.
    # Existing database accounts must use the dedicated Reset Password flow,
    # so profile/role edits cannot accidentally change credentials.
    if is_new and user.auth_source == 'database' and form.password.data:
        user.set_password(form.password.data)

    if is_new:
        db.session.add(user)

    return user


def is_admin_level_user(user: User) -> bool:
    return bool(user.is_super_admin or user.role_name == 'admin')


def role_id_is_admin_level(role_id: int | None) -> bool:
    if role_id is None:
        return False

    role = db.session.get(Role, role_id)
    return bool(role and role.name == 'admin')


def requested_admin_level(*, role_id: int | None, is_super_admin: bool) -> bool:
    return bool(is_super_admin or role_id_is_admin_level(role_id))


def active_super_admin_count() -> int:
    return User.query.filter(
        User.is_super_admin.is_(True),
        User.account_is_active.is_(True),
        User.deleted_at.is_(None),
    ).count()


def is_last_active_super_admin(user: User) -> bool:
    if not user.is_super_admin or not user.account_is_active or user.deleted_at is not None:
        return False

    return active_super_admin_count() <= 1


def _is_self_action(actor: User, target: User) -> bool:
    return bool(actor.id == target.id)


def _block_self_lifecycle(actor: User, target: User) -> tuple[bool, str | None]:
    if _is_self_action(actor, target):
        return False, 'You cannot change your own lifecycle status from User Management.'
    return True, None


def _block_deleted_target(target: User) -> tuple[bool, str | None]:
    if target.deleted_at is not None:
        return False, 'Deleted users cannot be modified.'
    return True, None


def _block_admin_level_management(actor: User, target: User) -> tuple[bool, str | None]:
    if is_admin_level_user(target) and not actor.is_super_admin:
        return False, 'Only a super admin can manage administrator-level accounts.'
    return True, None




def can_create_user(actor: User, *, requested_role_id: int | None, requested_is_super_admin: bool) -> tuple[bool, str | None]:
    if requested_admin_level(role_id=requested_role_id, is_super_admin=requested_is_super_admin) and not actor.is_super_admin:
        return False, 'Only a super admin can create administrator-level accounts.'

    return True, None

def can_activate_user(actor: User, target: User) -> tuple[bool, str | None]:
    allowed, message = _block_deleted_target(target)
    if not allowed:
        return allowed, message

    allowed, message = _block_self_lifecycle(actor, target)
    if not allowed:
        return allowed, message

    return _block_admin_level_management(actor, target)




def can_restore_user(actor: User, target: User) -> tuple[bool, str | None]:
    if not actor.has_permission('users.activate'):
        return False, 'You do not have permission to restore users.'

    if target.deleted_at is None:
        return False, 'This account is not deleted.'

    allowed, message = _block_self_lifecycle(actor, target)
    if not allowed:
        return allowed, message

    allowed, message = _block_admin_level_management(actor, target)
    if not allowed:
        return allowed, message

    username_conflict = User.query.filter(
        User.id != target.id,
        User.deleted_at.is_(None),
        User.username == target.username,
    ).first()
    if username_conflict:
        return False, 'An active user already uses this username. Update or remove the active account before restoring.'

    email_conflict = User.query.filter(
        User.id != target.id,
        User.deleted_at.is_(None),
        User.email == target.email,
    ).first()
    if email_conflict:
        return False, 'An active user already uses this email. Update or remove the active account before restoring.'

    return True, None

def can_deactivate_user(actor: User, target: User) -> tuple[bool, str | None]:
    allowed, message = _block_deleted_target(target)
    if not allowed:
        return allowed, message

    allowed, message = _block_self_lifecycle(actor, target)
    if not allowed:
        return allowed, message

    allowed, message = _block_admin_level_management(actor, target)
    if not allowed:
        return allowed, message

    if is_last_active_super_admin(target):
        return False, 'The last active super admin cannot be deactivated.'

    return True, None


def can_delete_user(actor: User, target: User) -> tuple[bool, str | None]:
    if not actor.has_permission('users.delete'):
        return False, 'You do not have permission to delete users.'

    allowed, message = _block_deleted_target(target)
    if not allowed:
        return allowed, message

    allowed, message = _block_self_lifecycle(actor, target)
    if not allowed:
        return allowed, message

    allowed, message = _block_admin_level_management(actor, target)
    if not allowed:
        return allowed, message

    if is_last_active_super_admin(target):
        return False, 'The last active super admin cannot be deleted.'

    return True, None


def can_reset_user_password(actor: User, target: User) -> tuple[bool, str | None]:
    if not actor.has_permission('users.reset_password'):
        return False, 'You do not have permission to reset user passwords.'

    allowed, message = _block_deleted_target(target)
    if not allowed:
        return allowed, message

    if target.auth_source != 'database':
        return False, 'Password reset is only available for database-managed users.'

    if _is_self_action(actor, target):
        return False, 'Use Account settings to change your own password.'

    return _block_admin_level_management(actor, target)


def can_edit_user(
    actor: User,
    target: User,
    *,
    requested_role_id: int | None,
    requested_is_active: bool,
    requested_is_super_admin: bool,
) -> tuple[bool, str | None]:
    if target.deleted_at is not None:
        return False, 'Deleted users cannot be edited.'

    requested_is_admin_level = requested_admin_level(
        role_id=requested_role_id,
        is_super_admin=requested_is_super_admin,
    )

    if _is_self_action(actor, target):
        security_fields_changed = (
            target.role_id != requested_role_id
            or target.account_is_active != requested_is_active
            or target.is_super_admin != requested_is_super_admin
        )
        if security_fields_changed:
            return False, 'You cannot change your own role, active status, or super admin flag from User Management.'

    if is_admin_level_user(target) and not actor.is_super_admin:
        return False, 'Only a super admin can edit administrator-level accounts.'

    if requested_is_admin_level and not actor.is_super_admin:
        return False, 'Only a super admin can grant administrator-level access.'

    if target.is_super_admin and target.account_is_active and is_last_active_super_admin(target):
        if not requested_is_active:
            return False, 'The last active super admin cannot be deactivated.'
        if not requested_is_super_admin:
            return False, 'The last active super admin cannot lose the super admin flag.'

    return True, None


def build_user_action_policies(actor: User | None, users: list[User]) -> dict[int, dict[str, Any]]:
    policies: dict[int, dict[str, Any]] = {}

    for user in users:
        if actor is None:
            policies[user.id] = {
                'can_edit': False,
                'can_reset_password': False,
                'can_activate': False,
                'can_deactivate': False,
                'can_delete': False,
                'can_restore': False,
                'reason': 'Authentication required.',
            }
            continue

        can_edit, edit_reason = can_edit_user(
            actor,
            user,
            requested_role_id=user.role_id,
            requested_is_active=user.account_is_active,
            requested_is_super_admin=user.is_super_admin,
        )
        can_reset, reset_reason = can_reset_user_password(actor, user)
        can_activate, activate_reason = can_activate_user(actor, user)
        can_deactivate, deactivate_reason = can_deactivate_user(actor, user)
        can_delete, delete_reason = can_delete_user(actor, user)
        can_restore, restore_reason = can_restore_user(actor, user)

        policies[user.id] = {
            'can_edit': can_edit,
            'edit_reason': edit_reason,
            'can_reset_password': can_reset,
            'reset_reason': reset_reason,
            'can_activate': can_activate,
            'activate_reason': activate_reason,
            'can_deactivate': can_deactivate,
            'deactivate_reason': deactivate_reason,
            'can_delete': can_delete,
            'delete_reason': delete_reason,
            'can_restore': can_restore,
            'restore_reason': restore_reason,
        }

    return policies


# Backward-compatible helper retained for older imports. New code should use the
# action-specific guards above.
def can_mutate_target(actor: User, target: User) -> tuple[bool, str | None]:
    return can_delete_user(actor, target)


def set_user_active(target: User, active: bool) -> None:
    target.account_is_active = active
    target.updated_at = datetime.now(UTC)


def soft_delete_user(target: User) -> None:
    now = datetime.now(UTC)
    target.account_is_active = False
    target.deleted_at = now
    target.updated_at = now




def restore_user(target: User) -> None:
    now = datetime.now(UTC)
    target.deleted_at = None
    target.account_is_active = True
    target.updated_at = now

def record_admin_event(*, actor: User | None, action: str, target: User | Role, summary: str, metadata: dict[str, Any] | None = None) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor else None
    event.target_type = target.__class__.__name__.lower()
    event.target_id = str(target.id)
    event.action = action
    event.summary = summary
    event.metadata_json = metadata
    db.session.add(event)
