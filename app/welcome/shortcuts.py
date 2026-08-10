from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from flask import url_for
from flask_login import current_user

WelcomeTarget = tuple[str | None, str]


def resolve_welcome_target(
    targets: Iterable[WelcomeTarget],
    has_permission: Callable[[str], bool],
) -> str | None:
    """Return the first target authorized for the current Welcome catalog context."""

    for permission_key, endpoint in targets:
        if permission_key is None or has_permission(permission_key):
            return endpoint
    return None


WELCOME_WORKSPACE_GROUP_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        'key': 'visibility',
        'eyebrow': 'Understand',
        'title': 'Visibility & Operational Insight',
        'description': (
            'Explore infrastructure posture, inventory, relationships, analytics, and prioritized operational insights.'
        ),
        'icon': 'scan-search',
    },
    {
        'key': 'operations',
        'eyebrow': 'Act',
        'title': 'Infrastructure Operations',
        'description': (
            'Open controlled workflows for integration management, synchronization, '
            'configuration, and infrastructure-changing activities.'
        ),
        'icon': 'workflow',
    },
    {
        'key': 'assurance',
        'eyebrow': 'Assure',
        'title': 'Governance & Reporting',
        'description': (
            'Review lifecycle controls, operational evidence, historical context, and management-ready outputs.'
        ),
        'icon': 'shield-check',
    },
    {
        'key': 'platform',
        'eyebrow': 'Administer',
        'title': 'Platform Administration',
        'description': (
            'Manage personal settings, access control, audit visibility, integrations, '
            'and platform configuration within assigned authority.'
        ),
        'icon': 'settings-2',
    },
)

WELCOME_SHORTCUT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        'title': 'Dashboards',
        'label': 'Operational Overview',
        'description': (
            'Review cluster posture, capacity risk, alerts, top consumers, '
            'reporting readiness, and prioritized actions.'
        ),
        'icon': 'layout-dashboard',
        'scope': 'Compute',
        'group': 'visibility',
        'targets': (('dashboard.view', 'kubernetes_dashboard.index'),),
    },
    {
        'title': 'K8s Inventory',
        'label': 'Asset Visibility',
        'description': (
            'Gain visibility into Kubernetes resources, their status, configuration, and relationships across connected clusters.'
        ),
        'icon': 'boxes',
        'scope': 'Compute',
        'group': 'visibility',
        'targets': (('inventory.view', 'inventory.overview'),),
    },
    {
        'title': 'K8s Analytics',
        'label': 'Operational Analytics',
        'description': (
            'Explore utilization, capacity, workload efficiency, storage, forecast risks, top consumers, alerts, and anomalies.'
        ),
        'icon': 'chart-column',
        'scope': 'Compute',
        'group': 'visibility',
        'targets': (('analytics.view', 'analytics.overview'),),
    },
    {
        'title': 'Intelligence',
        'label': 'Decision Support',
        'description': (
            'Identify operational findings, understand affected assets, and follow prioritized remediation guidance.'
        ),
        'icon': 'brain-circuit',
        'scope': 'Cross-domain',
        'group': 'visibility',
        'targets': (('intelligence.view', 'intelligence.recommendations'),),
    },
    {
        'title': 'Integrations',
        'label': 'Integration & Sync',
        'description': (
            'Manage Kubernetes, Prometheus, and Alertmanager integrations, connection readiness, bindings, and runtime status.'
        ),
        'icon': 'server-cog',
        'scope': 'Compute',
        'group': 'operations',
        'targets': (('clusters.view', 'integrations.kubernetes'),),
    },
    {
        'title': 'Platform Operations',
        'label': 'Execution & Administration',
        'description': (
            'Monitor background executions, govern data lifecycle, and manage advanced Kubernetes administration controls.'
        ),
        'icon': 'workflow',
        'scope': 'Platform',
        'group': 'operations',
        'targets': (
            ('jobs.view', 'platform_operations.overview.index'),
            ('jobs.configure', 'platform_operations.overview.index'),
            ('platform_operations.view_data_lifecycle', 'platform_operations.overview.index'),
            ('kubernetes_secrets.manage_reveal', 'platform_operations.overview.index'),
        ),
    },
    {
        'title': 'K8s Operations',
        'label': 'Controlled Workflows',
        'description': (
            'Run permission-aware configuration and protected infrastructure '
            'operations with validation, safeguards, and audit context.'
        ),
        'icon': 'wrench',
        'scope': 'Compute',
        'group': 'operations',
        'targets': (
            ('kubernetes_configmaps.view', 'kubernetes_operations.configmap_management'),
            ('kubernetes_configmaps.create', 'kubernetes_operations.configmap_management'),
            ('kubernetes_configmaps.update', 'kubernetes_operations.configmap_management'),
            ('kubernetes_configmaps.delete', 'kubernetes_operations.configmap_management'),
            ('kubernetes_secrets.view', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.create', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.replace', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.delete', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.reveal', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.approve_reveal', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.rotate_tls', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.bulk_rotate_tls', 'kubernetes_operations.secret_management'),
        ),
    },
    {
        'title': 'K8s Governance',
        'label': 'Policy & Lifecycle',
        'description': (
            'Review infrastructure governance posture, lifecycle exposure, policy '
            'context, and controlled remediation workflows.'
        ),
        'icon': 'shield-check',
        'scope': 'Compute',
        'group': 'assurance',
        'targets': (
            ('governance.view', 'governance.overview'),
            ('tls_certificates.view', 'governance.tls_certificates'),
        ),
    },
    {
        'title': 'Reports',
        'label': 'History & Management Output',
        'description': (
            'Open operational history, generated reports, templates, schedules, '
            'storage, retention, and management-ready outputs available to your role.'
        ),
        'icon': 'file-text',
        'scope': 'Cross-domain',
        'group': 'assurance',
        'targets': (
            ('reports.view', 'reports.overview'),
            ('reports.generate', 'reports.generate_report'),
            ('reports.manage_templates', 'reports.report_templates'),
            ('reports.manage_schedules', 'reports.schedules'),
            ('reports.manage_storage', 'reports.storage'),
        ),
    },
    {
        'title': 'Access',
        'label': 'Identity, Access & Audit',
        'description': (
            'Manage users, roles, permissions, authentication events, and operational '
            'audit records according to assigned authority.'
        ),
        'icon': 'users-round',
        'scope': 'Platform',
        'group': 'platform',
        'targets': (
            ('users.view', 'access.overview.index'),
            ('users.manage', 'access.overview.index'),
            ('roles.view', 'access.overview.index'),
            ('settings.view_operational_activity', 'access.overview.index'),
        ),
    },
    {
        'title': 'Settings',
        'label': 'Personal & System Settings',
        'description': (
            'Manage your account and preferences; authorized roles can also configure '
            'integrations and platform-level settings.'
        ),
        'icon': 'settings-2',
        'scope': 'Platform',
        'group': 'platform',
        'targets': ((None, 'settings.account'),),
    },
)


def build_welcome_workspace_groups() -> list[dict[str, Any]]:
    shortcuts_by_group: dict[str, list[dict[str, str]]] = {
        group['key']: [] for group in WELCOME_WORKSPACE_GROUP_DEFINITIONS
    }

    for definition in WELCOME_SHORTCUT_DEFINITIONS:
        resolved_endpoint = resolve_welcome_target(
            definition['targets'],
            current_user.has_permission,
        )

        if resolved_endpoint is None:
            continue

        shortcuts_by_group[definition['group']].append(
            {
                'title': definition['title'],
                'label': definition['label'],
                'description': definition['description'],
                'icon': definition['icon'],
                'scope': definition['scope'],
                'href': url_for(resolved_endpoint),
                'search_text': ' '.join(
                    (
                        definition['title'],
                        definition['label'],
                        definition['description'],
                        definition['scope'],
                    )
                ).lower(),
            }
        )

    groups: list[dict[str, Any]] = []

    for group_definition in WELCOME_WORKSPACE_GROUP_DEFINITIONS:
        shortcuts = shortcuts_by_group[group_definition['key']]
        if not shortcuts:
            continue

        groups.append(
            {
                **group_definition,
                'shortcuts': shortcuts,
                'shortcut_count': len(shortcuts),
            }
        )

    return groups
