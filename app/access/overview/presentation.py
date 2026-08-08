from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask_login import current_user

from app.extensions.db import db
from app.models import (
    ExternalIdentityLink,
    IdentityProvider,
    Notification,
    Permission,
    Role,
    RolePermission,
    User,
)


def _can(permission: str) -> bool:
    checker = getattr(current_user, 'has_permission', None)
    return bool(callable(checker) and checker(permission))


def _workspace_grid_classes(workspace_count: int, index: int) -> str:
    """Balance one-to-five permission-scoped workspace cards without empty columns."""

    if workspace_count <= 1:
        return 'md:col-span-2 xl:col-span-6'
    if workspace_count == 2:
        return 'xl:col-span-3'
    if workspace_count == 3:
        return 'xl:col-span-2'
    if workspace_count == 4:
        return 'xl:col-span-3'
    if workspace_count == 5:
        return 'xl:col-span-2' if index < 3 else 'xl:col-span-3'
    return 'xl:col-span-2'


def build_access_overview() -> dict[str, Any]:
    """Build a read-only Access landing summary from domain-owned sources.

    Access Overview composes permission-scoped posture only. User, identity,
    RBAC, and Activity Audit workspaces remain authoritative for mutations and
    detailed evidence.
    """

    workspaces: list[dict[str, Any]] = []
    boundaries: list[dict[str, str]] = []

    if _can('users.view'):
        active_users = User.query.filter(User.deleted_at.is_(None), User.account_is_active.is_(True)).count()
        total_users = User.query.filter(User.deleted_at.is_(None)).count()
        external_users = User.query.filter(
            User.deleted_at.is_(None),
            User.auth_source != 'database',
        ).count()
        super_admins = User.query.filter(
            User.deleted_at.is_(None),
            User.account_is_active.is_(True),
            User.is_super_admin.is_(True),
        ).count()
        workspaces.append(
            {
                'key': 'users',
                'label': 'User Management',
                'description': 'Account lifecycle, identity source, activation, and role assignment.',
                'icon': 'users-round',
                'status_label': 'Ready' if active_users else 'Review Required',
                'status_tone': 'normal' if active_users else 'warning',
                'metrics': (
                    ('users-round', 'Active Users', active_users),
                    ('contact-round', 'External Users', external_users),
                    ('shield-check', 'Super Admins', super_admins),
                ),
                'supporting_text': f'{total_users} registered account' + ('' if total_users == 1 else 's'),
                'boundary_label': 'Account lifecycle authority',
                'action_endpoint': 'users.index',
                'action_label': 'Open User Management',
            }
        )
        boundaries.append(
            {
                'title': 'Identity Lifecycle',
                'description': 'User Management owns account state, identity source, and role assignment.',
            }
        )

    if _can('users.manage'):
        enabled_providers = IdentityProvider.query.filter(IdentityProvider.enabled.is_(True)).count()
        total_providers = IdentityProvider.query.count()
        identity_links = ExternalIdentityLink.query.count()
        provider_status = 'Enabled' if enabled_providers else ('Configured' if total_providers else 'Not Configured')
        provider_tone = 'normal' if enabled_providers else ('info' if total_providers else 'unknown')
        workspaces.append(
            {
                'key': 'identity-providers',
                'label': 'Identity Providers',
                'description': 'LDAP and SSO configuration with external identity projection.',
                'icon': 'fingerprint',
                'status_label': provider_status,
                'status_tone': provider_tone,
                'metrics': (
                    ('badge-check', 'Enabled', enabled_providers),
                    ('settings-2', 'Configured', total_providers),
                    ('link', 'Identity Links', identity_links),
                ),
                'supporting_text': 'External providers are optional when local authentication is sufficient.',
                'boundary_label': 'Authentication source authority',
                'action_endpoint': 'users.providers',
                'action_label': 'Open Identity Providers',
            }
        )
        boundaries.append(
            {
                'title': 'Authentication Sources',
                'description': 'Identity Providers owns external source configuration and identity projection.',
            }
        )

    if _can('roles.view'):
        active_roles = Role.query.filter(Role.is_active.is_(True)).count()
        system_roles = Role.query.filter(Role.is_system.is_(True)).count()
        custom_roles = Role.query.filter(Role.is_system.is_(False)).count()
        total_permissions = Permission.query.count()
        permission_modules = Permission.query.with_entities(Permission.module).distinct().count()
        assigned_permissions = (
            db.session.query(RolePermission.permission_id)
            .distinct()
            .count()
        )
        workspaces.extend(
            [
                {
                    'key': 'roles',
                    'label': 'Roles & Access',
                    'description': 'Protected defaults and custom authorization role management.',
                    'icon': 'badge-check',
                    'status_label': 'Ready' if active_roles else 'Review Required',
                    'status_tone': 'normal' if active_roles else 'warning',
                    'metrics': (
                        ('badge-check', 'Active Roles', active_roles),
                        ('shield', 'System Roles', system_roles),
                        ('badge-plus', 'Custom Roles', custom_roles),
                    ),
                    'supporting_text': 'Inactive roles fail closed and do not grant permissions.',
                    'boundary_label': 'Authorization role authority',
                    'action_endpoint': 'access.roles.index',
                    'action_label': 'Open Roles & Access',
                },
                {
                    'key': 'permissions',
                    'label': 'Permission Catalog',
                    'description': 'Code-owned permissions grouped by module and role assignment.',
                    'icon': 'key-round',
                    'status_label': 'Registered' if total_permissions else 'Review Required',
                    'status_tone': 'normal' if total_permissions else 'warning',
                    'metrics': (
                        ('key-round', 'Permissions', total_permissions),
                        ('blocks', 'Modules', permission_modules),
                        ('link-2', 'Assigned', assigned_permissions),
                    ),
                    'supporting_text': 'Permission definitions remain code-owned; roles control assignment.',
                    'boundary_label': 'Code-owned permission registry',
                    'action_endpoint': 'access.permissions.index',
                    'action_label': 'Open Permission Catalog',
                },
            ]
        )
        boundaries.append(
            {
                'title': 'Authorization Policy',
                'description': 'Roles assign code-owned permissions; RBAC remains the enforcement authority.',
            }
        )

    if _can('settings.view_operational_activity'):
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        recent_events = Notification.query.filter(Notification.created_at >= cutoff).count()
        attention_events = Notification.query.filter(
            Notification.created_at >= cutoff,
            Notification.status.in_(['warning', 'error']),
        ).count()
        workspaces.append(
            {
                'key': 'activity-audit',
                'label': 'Activity Audit',
                'description': 'System-wide administrative and authentication evidence.',
                'icon': 'history',
                'status_label': 'Needs Review' if attention_events else 'Available',
                'status_tone': 'warning' if attention_events else 'normal',
                'metrics': (
                    ('history', 'Events · 24H', recent_events),
                    ('triangle-alert', 'Attention · 24H', attention_events),
                    ('scan-search', 'Evidence Scope', 'System'),
                ),
                'supporting_text': 'Personal notifications remain separate from administrative evidence.',
                'boundary_label': 'Administrative evidence',
                'action_endpoint': 'notifications.activity_log',
                'action_label': 'Open Activity Audit',
            }
        )
        boundaries.append(
            {
                'title': 'Audit Evidence',
                'description': 'Activity Audit owns system-wide administrative and authentication evidence.',
            }
        )

    workspace_count = len(workspaces)
    attention_workspace_count = sum(
        1 for workspace in workspaces if workspace['status_tone'] in {'warning', 'critical'}
    )

    for index, workspace in enumerate(workspaces):
        workspace['grid_classes'] = _workspace_grid_classes(workspace_count, index)

    overall_status_label = 'Review Required' if attention_workspace_count else 'Current'
    overall_status_tone = 'warning' if attention_workspace_count else 'normal'

    return {
        'workspace_count': workspace_count,
        'attention_workspace_count': attention_workspace_count,
        'overall_status_label': overall_status_label,
        'overall_status_tone': overall_status_tone,
        'hero_metrics': (
            {
                'icon': 'blocks',
                'label': 'Workspaces',
                'value': workspace_count,
                'description': 'Visible access domains',
            },
            {
                'icon': 'triangle-alert',
                'label': 'Review',
                'value': attention_workspace_count,
                'description': 'Domains needing review',
            },
        ),
        'workspaces': workspaces,
        'boundaries': boundaries,
    }
