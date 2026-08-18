from __future__ import annotations

from typing import Any

from flask_login import current_user

from app.access.activity_audit.service import get_activity_audit_summary
from app.access.permissions.service import build_permission_registry_snapshot
from app.access.roles.presentation import build_roles_index_context
from app.access.users.access_summary import build_identity_provider_summary, build_user_access_summary


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


def _user_supporting_text(summary: dict[str, Any]) -> str:
    if not summary['active']:
        return 'No active user account is available; review account lifecycle before relying on Access controls.'
    if not summary['active_super_admins']:
        return 'No active break-glass super admin is available; restore protected administrative authority.'
    if summary['access_review']:
        return (
            f'{summary["access_review"]} account admission issue(s) require review across RBAC, '
            'external identity, or emergency-access state.'
        )
    return (
        f'{summary["total"]} registered account(s) with {summary["active_super_admins"]} active Local Database '
        'break-glass super admin(s).'
    )


def _identity_provider_supporting_text(summary: dict[str, Any]) -> str:
    if not summary['total']:
        return 'External providers are optional while local authentication remains sufficient.'
    if summary['enabled_incomplete']:
        return f'{summary["enabled_incomplete"]} enabled provider(s) have incomplete connection configuration.'
    if summary['jit_policy_review']:
        return f'{summary["jit_policy_review"]} enabled JIT provider(s) need default-role or admission-policy review.'
    if summary['enabled']:
        return (
            'Enabled providers have complete configuration and admission policy at the stored-configuration boundary.'
        )
    return 'Providers are stored but disabled; enable them only after configuration and admission policy are ready.'


def _role_supporting_text(summary: dict[str, Any]) -> str:
    if not summary['active_roles']:
        return 'No active role is available; role-based authorization cannot grant access.'
    if summary['baseline_drift_count']:
        return f'{summary["baseline_drift_count"]} protected role baseline finding(s) require explicit RBAC convergence review.'
    if summary['inactive_assigned_users']:
        return (
            f'{summary["inactive_assigned_users"]} user assignment(s) point to inactive roles '
            'and therefore fail closed.'
        )
    return 'Protected defaults match the source-controlled baseline; custom role delegation remains ceiling-bound.'


def _permission_supporting_text(summary: dict[str, Any]) -> str:
    if summary['drift_count']:
        return (
            f'{summary["drift_count"]} permission contract(s) differ from the code-owned registry; '
            'run the explicit RBAC convergence workflow after review.'
        )
    return (
        f'{summary["role_mappings"]} role-permission mapping(s); '
        f'{summary["unused_contracts"]} canonical permission contract(s) currently unassigned.'
    )


def _activity_supporting_text(summary: dict[str, Any]) -> str:
    if summary['attention_24h']:
        return f'{summary["attention_24h"]} warning/error event(s) were recorded in the last 24 hours.'
    return 'No warning/error administrative evidence was recorded in the last 24 hours.'


def build_access_overview() -> dict[str, Any]:
    """Compose read-only Access posture from domain-owned summary contracts.

    User, identity-provider, RBAC, permission-registry, and Activity Audit
    workspaces remain authoritative for both detailed evidence and mutations.
    This page only projects their permission-scoped summaries.
    """

    workspaces: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []

    if _can('users.view'):
        users = build_user_access_summary()
        workspaces.append(
            {
                'key': 'users',
                'label': 'User Management',
                'description': 'Account lifecycle, identity source, activation, and role assignment.',
                'icon': 'users-round',
                'status_label': users['posture_label'],
                'status_tone': users['posture_tone'],
                'metrics': (
                    ('users-round', 'Active Users', users['active']),
                    ('contact-round', 'External Users', users['external']),
                    ('shield-check', 'Local Super Admins', users['active_super_admins']),
                ),
                'supporting_text': _user_supporting_text(users),
                'boundary_label': 'Account lifecycle authority',
                'action_endpoint': 'users.index',
                'action_label': 'Open User Management',
            }
        )
        boundaries.append(
            {
                'title': 'Identity Lifecycle',
                'description': 'User Management owns account state, role assignment, and break-glass authority.',
                'status_label': users['posture_label'],
                'status_tone': users['posture_tone'],
            }
        )

    if _can('identity_providers.view'):
        providers = build_identity_provider_summary()
        workspaces.append(
            {
                'key': 'identity-providers',
                'label': 'Identity Providers',
                'description': 'LDAP and SSO configuration with external identity projection.',
                'icon': 'fingerprint',
                'status_label': providers['posture_label'],
                'status_tone': providers['posture_tone'],
                'metrics': (
                    ('badge-check', 'Enabled', providers['enabled']),
                    ('settings-2', 'Configured', providers['configured']),
                    ('link', 'Identity Links', providers['identity_links']),
                ),
                'supporting_text': _identity_provider_supporting_text(providers),
                'boundary_label': 'Authentication source authority',
                'action_endpoint': 'identity_providers.index',
                'action_label': 'Open Identity Providers',
            }
        )
        boundaries.append(
            {
                'title': 'Authentication Sources',
                'description': (
                    'Identity Providers owns external source configuration, admission policy, and projection.'
                ),
                'status_label': providers['posture_label'],
                'status_tone': providers['posture_tone'],
            }
        )

    if _can('roles.view'):
        role_summary = build_roles_index_context(can_manage_roles=False)['summary']
        permission_summary = build_permission_registry_snapshot()['summary']
        workspaces.extend(
            [
                {
                    'key': 'roles',
                    'label': 'Roles & Access',
                    'description': 'Protected defaults and custom authorization role management.',
                    'icon': 'badge-check',
                    'status_label': role_summary['posture_label'],
                    'status_tone': role_summary['posture_tone'],
                    'metrics': (
                        ('badge-check', 'Active Roles', role_summary['active_roles']),
                        ('shield', 'System Roles', role_summary['system_roles']),
                        ('badge-plus', 'Custom Roles', role_summary['custom_roles']),
                    ),
                    'supporting_text': _role_supporting_text(role_summary),
                    'boundary_label': 'Authorization role authority',
                    'action_endpoint': 'access.roles.index',
                    'action_label': 'Open Roles & Access',
                },
                {
                    'key': 'permissions',
                    'label': 'Permission Catalog',
                    'description': 'Code-owned permission contracts, registry alignment, and role coverage.',
                    'icon': 'key-round',
                    'status_label': permission_summary['posture_label'],
                    'status_tone': permission_summary['posture_tone'],
                    'metrics': (
                        ('key-round', 'Permissions', permission_summary['canonical_permissions']),
                        ('blocks', 'Modules', permission_summary['control_modules']),
                        ('triangle-alert', 'Drift', permission_summary['drift_count']),
                    ),
                    'supporting_text': _permission_supporting_text(permission_summary),
                    'boundary_label': 'Code-owned permission registry',
                    'action_endpoint': 'access.permissions.index',
                    'action_label': 'Open Permission Catalog',
                },
            ]
        )
        authorization_review = bool(
            role_summary['posture_tone'] == 'warning' or permission_summary['posture_tone'] == 'warning'
        )
        boundaries.append(
            {
                'title': 'Authorization Policy',
                'description': (
                    'Roles assign code-owned permissions; inactive roles fail closed and registry drift is explicit.'
                ),
                'status_label': 'Review Required' if authorization_review else 'Current',
                'status_tone': 'warning' if authorization_review else 'normal',
            }
        )

    if _can('activity_audit.view'):
        activity = get_activity_audit_summary()
        workspaces.append(
            {
                'key': 'activity-audit',
                'label': 'Activity Audit',
                'description': 'System-wide administrative and authentication evidence.',
                'icon': 'history',
                'status_label': activity['posture_label'],
                'status_tone': activity['posture_tone'],
                'metrics': (
                    ('history', 'Events · 24H', activity['events_24h']),
                    ('triangle-alert', 'Attention · 24H', activity['attention_24h']),
                    ('users-round', 'Actors · 24H', activity['actors_24h']),
                ),
                'supporting_text': _activity_supporting_text(activity),
                'boundary_label': 'Administrative evidence',
                'action_endpoint': 'access.activity_audit.index',
                'action_label': 'Open Activity Audit',
            }
        )
        boundaries.append(
            {
                'title': 'Audit Evidence',
                'description': (
                    'Activity Audit owns retained administrative and authentication evidence and actor semantics.'
                ),
                'status_label': activity['posture_label'],
                'status_tone': activity['posture_tone'],
            }
        )

    workspace_count = len(workspaces)
    warning_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'warning')
    critical_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'critical')
    unknown_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'unknown')
    attention_workspace_count = warning_workspace_count + critical_workspace_count

    for index, workspace in enumerate(workspaces):
        workspace['grid_classes'] = _workspace_grid_classes(workspace_count, index)

    if critical_workspace_count:
        overall_status_label, overall_status_tone = 'Critical Review', 'critical'
    elif warning_workspace_count:
        overall_status_label, overall_status_tone = 'Review Required', 'warning'
    else:
        overall_status_label, overall_status_tone = 'Current', 'normal'

    return {
        'workspace_count': workspace_count,
        'attention_workspace_count': attention_workspace_count,
        'unknown_workspace_count': unknown_workspace_count,
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
