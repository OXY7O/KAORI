from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.common.pagination import (
    PER_PAGE_OPTIONS,
    build_pagination_window,
    normalize_per_page,
    positive_int,
)
from app.extensions.db import db
from app.models import AuditEvent, ExternalIdentityLink, IdentityProvider, Role, User

if TYPE_CHECKING:
    from app.users.forms import UserForm

PROVIDER_TYPE_OPTIONS = ['all', 'ldap', 'google_oidc', 'github_oauth']
PROVIDER_STATE_OPTIONS = ['all', 'enabled', 'disabled']


def normalize_provider_filters(args: Mapping[str, str | None]) -> dict[str, Any]:
    provider_type = (args.get('provider_type') or 'all').strip().lower()
    state = (args.get('state') or 'all').strip().lower()
    return {
        'search': (args.get('search') or '').strip(),
        'provider_type': provider_type if provider_type in PROVIDER_TYPE_OPTIONS else 'all',
        'state': state if state in PROVIDER_STATE_OPTIONS else 'all',
        'page': positive_int(args.get('page'), 1),
        'per_page': normalize_per_page(args.get('per_page')),
    }


def _provider_configuration_complete(provider: IdentityProvider) -> bool:
    if provider.provider_type == 'ldap':
        return all(
            str(value or '').strip()
            for value in (
                provider.server_uri,
                provider.base_dn,
                provider.bind_dn,
                provider.bind_password_env,
            )
        )
    if provider.provider_type in {'google_oidc', 'github_oauth'}:
        return all(str(value or '').strip() for value in (provider.oidc_client_id, provider.oidc_client_secret_env))
    return False


def present_identity_provider(provider: IdentityProvider, *, identity_links: int) -> dict[str, Any]:
    type_catalog = {
        'ldap': {'label': 'LDAP / Active Directory', 'short_label': 'LDAP', 'icon': 'network'},
        'google_oidc': {'label': 'Google OpenID Connect', 'short_label': 'Google OIDC', 'icon': 'chrome'},
        'github_oauth': {'label': 'GitHub OAuth', 'short_label': 'GitHub OAuth', 'icon': 'github'},
    }
    provider_type = type_catalog.get(
        provider.provider_type,
        {'label': 'External Provider', 'short_label': 'External', 'icon': 'fingerprint'},
    )
    configuration_complete = _provider_configuration_complete(provider)

    if provider.provider_type == 'ldap':
        access_model = {
            'label': 'Administrative Provisioning',
            'description': 'Directory identities are projected into KAORI before authentication.',
        }
        credential_reference = provider.bind_password_env or 'Not Configured'
        connection = provider.server_uri or 'Not Configured'
        projection = 'Directory Provisioning'
    elif provider.jit_enabled:
        access_model = {
            'label': 'Controlled JIT',
            'description': 'Approved external identities may create a KAORI account with the configured default role.',
        }
        credential_reference = provider.oidc_client_secret_env or 'Not Configured'
        connection = 'External OAuth / OIDC Application'
        projection = 'Controlled JIT'
    else:
        access_model = {
            'label': 'Pre-Provisioned SSO',
            'description': 'Only external identities already linked to a KAORI account may authenticate.',
        }
        credential_reference = provider.oidc_client_secret_env or 'Not Configured'
        connection = 'External OAuth / OIDC Application'
        projection = 'Pre-Provisioned'

    return {
        'record': provider,
        'type': provider_type,
        'configuration': {
            'label': 'Configured' if configuration_complete else 'Incomplete',
            'tone': 'normal' if configuration_complete else 'warning',
            'icon': 'circle-check' if configuration_complete else 'triangle-alert',
            'complete': configuration_complete,
        },
        'state': {
            'label': 'Enabled' if provider.enabled else 'Disabled',
            'tone': 'normal' if provider.enabled else 'unknown',
            'icon': 'power' if provider.enabled else 'power-off',
        },
        'identity_links': int(identity_links or 0),
        'access_model': access_model,
        'credential_reference': credential_reference,
        'connection': connection,
        'projection': projection,
        'validation': {
            'label': 'On Demand',
            'description': 'Validation runs live and is not stored as durable provider readiness evidence.',
        },
    }


def build_identity_provider_payload(filters: dict[str, Any]) -> dict[str, Any]:
    all_providers = IdentityProvider.query.order_by(
        IdentityProvider.provider_type.asc(), IdentityProvider.display_name.asc()
    ).all()
    link_count_rows = (
        db.session.query(ExternalIdentityLink.provider_id, func.count(ExternalIdentityLink.id))
        .group_by(ExternalIdentityLink.provider_id)
        .all()
    )
    link_counts = {int(provider_id): int(count or 0) for provider_id, count in link_count_rows}

    provider_rows = [
        present_identity_provider(provider, identity_links=link_counts.get(provider.id, 0))
        for provider in all_providers
    ]

    search = filters['search'].lower()
    if search:
        provider_rows = [
            row
            for row in provider_rows
            if search
            in ' '.join(
                (
                    row['record'].display_name or '',
                    row['record'].key or '',
                    row['type']['label'],
                    row['access_model']['label'],
                )
            ).lower()
        ]
    if filters['provider_type'] != 'all':
        provider_rows = [row for row in provider_rows if row['record'].provider_type == filters['provider_type']]
    if filters['state'] == 'enabled':
        provider_rows = [row for row in provider_rows if row['record'].enabled]
    elif filters['state'] == 'disabled':
        provider_rows = [row for row in provider_rows if not row['record'].enabled]

    matching_count = len(provider_rows)
    pagination = build_pagination_window(
        total_items=matching_count,
        page=filters['page'],
        per_page=filters['per_page'],
    )
    provider_rows = provider_rows[pagination.offset : pagination.offset + pagination.per_page]

    all_presentations = [
        present_identity_provider(provider, identity_links=link_counts.get(provider.id, 0))
        for provider in all_providers
    ]
    configured_count = sum(1 for row in all_presentations if row['configuration']['complete'])
    enabled_count = sum(1 for provider in all_providers if provider.enabled)
    ldap_count = sum(1 for provider in all_providers if provider.provider_type == 'ldap')
    sso_count = len(all_providers) - ldap_count
    identity_links = sum(link_counts.values())
    ldap_provider_ids = {provider.id for provider in all_providers if provider.provider_type == 'ldap'}
    ldap_identity_links = sum(count for provider_id, count in link_counts.items() if provider_id in ldap_provider_ids)

    if not all_providers:
        posture_label, posture_tone = 'Not Configured', 'unknown'
    elif configured_count < len(all_providers):
        posture_label, posture_tone = 'Review Required', 'warning'
    else:
        posture_label, posture_tone = 'Configured', 'normal'

    return {
        'provider_rows': provider_rows,
        'summary': {
            'total': len(all_providers),
            'configured': configured_count,
            'enabled': enabled_count,
            'ldap': ldap_count,
            'sso': sso_count,
            'identity_links': identity_links,
            'ldap_identity_links': ldap_identity_links,
            'matching': matching_count,
            'posture_label': posture_label,
            'posture_tone': posture_tone,
        },
        'filters': {**filters, 'page': pagination.page, 'per_page': pagination.per_page},
        'pagination': pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'pagination_query': {
            'per_page': pagination.per_page,
            'search': filters['search'],
            'provider_type': filters['provider_type'],
            'state': filters['state'],
        },
        'provider_type_options': PROVIDER_TYPE_OPTIONS,
        'provider_state_options': PROVIDER_STATE_OPTIONS,
    }


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
