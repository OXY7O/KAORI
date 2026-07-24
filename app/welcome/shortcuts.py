from __future__ import annotations

from typing import Any

from flask import url_for
from flask_login import current_user

WELCOME_WORKSPACE_GROUP_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        'key': 'visibility',
        'eyebrow': 'Understand',
        'title': 'Visibility & Operational Insight',
        'description': (
            'Understand infrastructure posture, resource relationships, operational trends, and prioritized signals from one place.'
        ),
        'icon': 'scan-search',
    },
    {
        'key': 'operations',
        'eyebrow': 'Act',
        'title': 'Infrastructure Operations',
        'description': (
            'Manage integrations, synchronization, protected configuration changes, '
            'and other controlled operational workflows.'
        ),
        'icon': 'workflow',
    },
    {
        'key': 'assurance',
        'eyebrow': 'Assure',
        'title': 'Governance & Reporting',
        'description': (
            'Review governance posture, lifecycle exposure, operational evidence, history, and management-ready reporting.'
        ),
        'icon': 'shield-check',
    },
    {
        'key': 'platform',
        'eyebrow': 'Administer',
        'title': 'Platform Administration',
        'description': (
            'Administer identity, access, audit visibility, personal preferences, and '
            'platform configuration within assigned authority.'
        ),
        'icon': 'settings-2',
    },
)

WELCOME_SHORTCUT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        'title': 'Dashboards',
        'label': 'Kubernetes Operations',
        'description': (
            'Review cluster health, capacity risk, active alerts, top consumers, '
            'readiness, and prioritized operational actions.'
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
            'Explore Kubernetes resources, status, configuration, ownership, and relationships across connected clusters.'
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
            'Analyze utilization, capacity, workload efficiency, storage pressure, forecast risk, top consumers, alerts, and anomalies.'
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
            'Review operational findings, affected assets, confidence context, and prioritized remediation guidance.'
        ),
        'icon': 'brain-circuit',
        'scope': 'Cross-domain',
        'group': 'visibility',
        'targets': (('intelligence.view', 'intelligence.recommendations'),),
    },
    {
        'title': 'Integrations',
        'label': 'Provider Connectivity',
        'description': (
            'Manage Kubernetes, Prometheus, and Alertmanager connections, bindings, compatibility, readiness, and runtime health.'
        ),
        'icon': 'plug',
        'scope': 'Platform',
        'group': 'operations',
        'targets': (('settings.manage_integrations', 'integrations.overview'),),
    },
    {
        'title': 'K8s Operations',
        'label': 'Controlled Workflows',
        'description': (
            'Execute permission-aware infrastructure changes with validation, '
            'safeguards, approval boundaries, and audit context.'
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
        'title': 'Platform Operations',
        'label': 'Jobs & Inventory Sync',
        'description': (
            'Review asynchronous execution history and control scheduled or on-demand inventory synchronization across eligible clusters.'
        ),
        'icon': 'workflow',
        'scope': 'Platform',
        'group': 'operations',
        'targets': (
            ('jobs.view', 'integrations.jobs'),
            ('settings.manage_integrations', 'settings.inventory_sync.index'),
        ),
    },
    {
        'title': 'K8s Governance',
        'label': 'Policy & Lifecycle',
        'description': (
            'Review governance posture, lifecycle exposure, policy context, '
            'certificate risk, and controlled remediation workflows.'
        ),
        'icon': 'shield-check',
        'scope': 'Cross-domain',
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
            'Access operational reports, generation history, templates, schedules, '
            'storage, retention, and management-ready outputs.'
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
            'Manage users, roles, permissions, authentication activity, and '
            'operational audit records within assigned authority.'
        ),
        'icon': 'users-round',
        'scope': 'Platform',
        'group': 'platform',
        'targets': (
            ('users.view', 'users.index'),
            ('roles.view', 'settings.roles'),
            ('settings.view_operational_activity', 'notifications.activity_log'),
        ),
    },
    {
        'title': 'Settings',
        'label': 'Personal & System Settings',
        'description': (
            'Manage account preferences and, when authorized, platform-wide '
            'configuration and operational settings.'
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
        resolved_endpoint: str | None = None

        for permission_key, endpoint in definition['targets']:
            if permission_key is None or current_user.has_permission(permission_key):
                resolved_endpoint = endpoint
                break

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
