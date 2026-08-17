from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select

from app.extensions.db import db
from app.models import AuditEvent, Role, User

if TYPE_CHECKING:
    from app.users.forms import UserForm


def normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or '').strip()
    return normalized or None


def lock_active_super_admin_boundary(target: User) -> None:
    """Serialize lifecycle mutations that could remove active super-admin authority.

    Presentation checks remain lock-free. Mutation routes call this immediately
    before the final guardrail check so concurrent deactivate/delete/demotion
    requests cannot each observe a stale active-local-super-admin count.
    """

    if (
        target.auth_source != 'database'
        or not target.is_super_admin
        or not target.account_is_active
        or target.deleted_at is not None
    ):
        return

    statement = (
        select(User)
        .where(
            User.auth_source == 'database',
            User.is_super_admin.is_(True),
            User.account_is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .with_for_update()
    )
    db.session.execute(statement).scalars().all()
    db.session.refresh(target)


def assign_user_form_choices(form: UserForm, *, include_admin_roles: bool = True) -> None:
    query = Role.query.filter_by(is_active=True)
    if not include_admin_roles:
        query = query.filter(Role.name != 'admin')

    roles = query.order_by(Role.display_name.asc()).all()
    form.role_id.choices = [(str(role.id), role.display_name) for role in roles]


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


def create_or_update_user(form: UserForm, user: User | None = None) -> User:
    is_new = user is None
    if user is None:
        user = User()

    username = (form.username.data or '').strip()
    email = (form.email.data or '').strip().lower()
    role_id = form.role_id.data
    if not username or not email or role_id is None:
        raise ValueError('Validated user form is missing required identity or role data.')

    user.username = username
    user.email = email
    user.display_name = normalize_optional_text(form.display_name.data)
    if is_new:
        user.auth_source = (form.auth_source.data or 'database').strip() or 'database'
        user.external_id = normalize_optional_text(form.external_id.data)
    user.role_id = role_id
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


def active_local_super_admin_count() -> int:
    return User.query.filter(
        User.auth_source == 'database',
        User.is_super_admin.is_(True),
        User.account_is_active.is_(True),
        User.deleted_at.is_(None),
    ).count()


def is_last_active_local_super_admin(user: User) -> bool:
    if (
        user.auth_source != 'database'
        or not user.is_super_admin
        or not user.account_is_active
        or user.deleted_at is not None
    ):
        return False

    return active_local_super_admin_count() <= 1


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


def can_create_user(
    actor: User, *, requested_role_id: int | None, requested_is_super_admin: bool
) -> tuple[bool, str | None]:
    if not actor.has_permission('users.manage'):
        return False, 'You do not have permission to create users.'

    if (
        requested_admin_level(role_id=requested_role_id, is_super_admin=requested_is_super_admin)
        and not actor.is_super_admin
    ):
        return False, 'Only a super admin can create administrator-level accounts.'

    return True, None


def can_activate_user(actor: User, target: User) -> tuple[bool, str | None]:
    if not actor.has_permission('users.activate'):
        return False, 'You do not have permission to activate users.'

    allowed, message = _block_deleted_target(target)
    if not allowed:
        return allowed, message

    allowed, message = _block_self_lifecycle(actor, target)
    if not allowed:
        return allowed, message

    allowed, message = _block_admin_level_management(actor, target)
    if not allowed:
        return allowed, message

    if target.is_super_admin and target.auth_source != 'database':
        return False, 'Clear the invalid external Super Admin flag before activating this account.'

    return True, None


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
    if not actor.has_permission('users.activate'):
        return False, 'You do not have permission to deactivate users.'

    allowed, message = _block_deleted_target(target)
    if not allowed:
        return allowed, message

    allowed, message = _block_self_lifecycle(actor, target)
    if not allowed:
        return allowed, message

    allowed, message = _block_admin_level_management(actor, target)
    if not allowed:
        return allowed, message

    if is_last_active_local_super_admin(target):
        return False, 'The last active Local Database super admin cannot be deactivated.'

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

    if is_last_active_local_super_admin(target):
        return False, 'The last active Local Database super admin cannot be deleted.'

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
    if not actor.has_permission('users.manage'):
        return False, 'You do not have permission to edit users.'

    if target.deleted_at is not None:
        return False, 'Deleted users cannot be edited.'

    requested_is_admin_level = requested_admin_level(
        role_id=requested_role_id,
        is_super_admin=requested_is_super_admin,
    )

    if requested_is_super_admin and target.auth_source != 'database':
        return False, 'Super Admin authority is reserved for Local Database break-glass accounts.'

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

    if (
        target.auth_source == 'database'
        and target.is_super_admin
        and target.account_is_active
        and is_last_active_local_super_admin(target)
    ):
        if not requested_is_active:
            return False, 'The last active Local Database super admin cannot be deactivated.'
        if not requested_is_super_admin:
            return False, 'The last active Local Database super admin cannot lose the super admin flag.'

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
            requested_is_super_admin=user.is_super_admin if user.auth_source == 'database' else False,
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
    # Restore and Activate are separate administrative decisions. A restored
    # account returns to inactive administration until activation is explicit.
    target.account_is_active = False
    target.updated_at = now


def record_admin_event(
    *, actor: User | None, action: str, target: User | Role, summary: str, metadata: dict[str, Any] | None = None
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor else None
    event.target_type = target.__class__.__name__.lower()
    event.target_id = str(target.id)
    event.action = action
    event.summary = summary
    event.metadata_json = metadata
    db.session.add(event)
