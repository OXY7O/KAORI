from __future__ import annotations

from typing import Any

from flask_login import current_user

from app.models import IdentityProvider, Permission, Role, User


def _can(permission: str) -> bool:
    checker = getattr(current_user, 'has_permission', None)
    return bool(callable(checker) and checker(permission))


def build_access_overview() -> dict[str, Any]:
    """Build a read-only Access landing summary from domain-owned sources."""

    workspaces: list[dict[str, Any]] = []
    posture_candidates: list[dict[str, Any]] = []

    if _can('users.view'):
        active_users = User.query.filter(User.deleted_at.is_(None), User.account_is_active.is_(True)).count()
        total_users = User.query.filter(User.deleted_at.is_(None)).count()
        posture_candidates.append(
            {
                'icon': 'users-round',
                'label': 'Active Users',
                'value': active_users,
            }
        )
        workspaces.append(
            {
                'label': 'User Management',
                'description': 'Manage account lifecycle, identity source, and role assignment.',
                'icon': 'users-round',
                'metric_label': 'Active Users',
                'metric_value': active_users,
                'secondary_label': 'Registered',
                'secondary_value': total_users,
                'action_endpoint': 'users.index',
                'action_label': 'Open User Management',
            }
        )

    if _can('users.manage'):
        enabled_providers = IdentityProvider.query.filter(IdentityProvider.enabled.is_(True)).count()
        total_providers = IdentityProvider.query.count()
        posture_candidates.append(
            {
                'icon': 'fingerprint',
                'label': 'Providers',
                'value': enabled_providers,
            }
        )
        workspaces.append(
            {
                'label': 'Identity Providers',
                'description': 'Administer LDAP and SSO provider configuration and identity projection.',
                'icon': 'fingerprint',
                'metric_label': 'Enabled Providers',
                'metric_value': enabled_providers,
                'secondary_label': 'Configured',
                'secondary_value': total_providers,
                'action_endpoint': 'users.providers',
                'action_label': 'Open Identity Providers',
            }
        )

    if _can('roles.view'):
        active_roles = Role.query.filter(Role.is_active.is_(True)).count()
        total_permissions = Permission.query.count()
        posture_candidates.append(
            {
                'icon': 'badge-check',
                'label': 'Active Roles',
                'value': active_roles,
            }
        )
        workspaces.extend(
            [
                {
                    'label': 'Roles & Access',
                    'description': 'Review protected defaults and manage custom authorization roles.',
                    'icon': 'badge-check',
                    'metric_label': 'Active Roles',
                    'metric_value': active_roles,
                    'secondary_label': 'Custom Roles',
                    'secondary_value': Role.query.filter(Role.is_system.is_(False)).count(),
                    'action_endpoint': 'access.roles.index',
                    'action_label': 'Open Roles & Access',
                },
                {
                    'label': 'Permission Catalog',
                    'description': 'Inspect the code-owned permission registry and role assignments.',
                    'icon': 'key-round',
                    'metric_label': 'Permissions',
                    'metric_value': total_permissions,
                    'secondary_label': 'Modules',
                    'secondary_value': Permission.query.with_entities(Permission.module).distinct().count(),
                    'action_endpoint': 'access.permissions.index',
                    'action_label': 'Open Permission Catalog',
                },
            ]
        )

    if _can('settings.view_operational_activity'):
        posture_candidates.append(
            {
                'icon': 'history',
                'label': 'Audit Scope',
                'value': 'System',
            }
        )
        workspaces.append(
            {
                'label': 'Activity Audit',
                'description': 'Review system-wide administrative and authentication evidence.',
                'icon': 'history',
                'metric_label': 'Evidence Scope',
                'metric_value': 'System',
                'secondary_label': 'Mode',
                'secondary_value': 'Read Only',
                'action_endpoint': 'notifications.activity_log',
                'action_label': 'Open Activity Audit',
            }
        )

    secondary_posture = next(iter(posture_candidates), None) or {
        'icon': 'shield-check',
        'label': 'Mode',
        'value': 'Read Only',
        'description': 'Overview posture only',
    }
    hero_metrics = [
        {
            'icon': 'blocks',
            'label': 'Workspaces',
            'value': len(workspaces),
            'description': 'Visible access domains',
        },
        {
            **secondary_posture,
            'description': {
                'Active Users': 'Enabled account identities',
                'Providers': 'Enabled identity sources',
                'Active Roles': 'Enabled authorization roles',
                'Audit Scope': 'Administrative evidence scope',
            }.get(secondary_posture['label'], secondary_posture.get('description', 'Current access posture')),
        },
    ]

    return {
        'workspace_count': len(workspaces),
        'workspaces': workspaces,
        'hero_metrics': hero_metrics,
    }
