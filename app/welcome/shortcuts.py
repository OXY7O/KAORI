from __future__ import annotations

from typing import Any

from flask import url_for
from flask_login import current_user

WELCOME_SHORTCUT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        'title': 'Kubernetes Operations Dashboard',
        'label': 'Command center',
        'description': (
            'Review cluster health, capacity risk, alerts, top consumers, '
            'reporting readiness, and prioritized actions.'
        ),
        'icon': 'layout-dashboard',
        'asset': 'Kubernetes',
        'targets': (('dashboard.view', 'kubernetes_dashboard.index'),),
    },
    {
        'title': 'Kubernetes Cluster',
        'label': 'Connection & sync',
        'description': (
            'Review registered clusters, connectivity, inventory synchronization, '
            'and integration readiness.'
        ),
        'icon': 'server-cog',
        'asset': 'Kubernetes',
        'targets': (('clusters.view', 'cluster.list_clusters'),),
    },
    {
        'title': 'Kubernetes Inventory',
        'label': 'Asset visibility',
        'description': (
            'Explore clusters, nodes, namespaces, workloads, Pods, services, '
            'ingress, storage, and configuration relationships.'
        ),
        'icon': 'boxes',
        'asset': 'Kubernetes',
        'targets': (('inventory.view', 'inventory.overview'),),
    },
    {
        'title': 'Kubernetes Analytics',
        'label': 'Analytics',
        'description': (
            'Analyze utilization, capacity, workload efficiency, storage, forecast '
            'risk, top consumers, alerts, and anomalies.'
        ),
        'icon': 'chart-column',
        'asset': 'Kubernetes',
        'targets': (('analytics.view', 'analytics.overview'),),
    },
    {
        'title': 'Kubernetes Operations',
        'label': 'Controlled actions',
        'description': (
            'Run permission-aware operational workflows such as validated Secret '
            'management and TLS rotation.'
        ),
        'icon': 'wrench',
        'asset': 'Kubernetes',
        'targets': (
            ('kubernetes_configmaps.view', 'kubernetes_operations.configmap_management'),
            ('kubernetes_configmaps.create', 'kubernetes_operations.configmap_management'),
            ('kubernetes_configmaps.update', 'kubernetes_operations.configmap_management'),
            ('kubernetes_configmaps.delete', 'kubernetes_operations.configmap_management'),
            ('kubernetes_secrets.view', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.create', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.replace', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.reveal', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.approve_reveal', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.rotate_tls', 'kubernetes_operations.secret_management'),
            ('kubernetes_secrets.bulk_rotate_tls', 'kubernetes_operations.secret_management'),
        ),
    },
    {
        'title': 'Intelligence',
        'label': 'Recommendations',
        'description': (
            'Review contextual recommendations, alert intelligence, rule definitions, '
            'impacted assets, and remediation guidance.'
        ),
        'icon': 'brain-circuit',
        'asset': 'Cross-domain',
        'targets': (('intelligence.view', 'intelligence.recommendations'),),
    },
    {
        'title': 'Governance',
        'label': 'Policy & lifecycle',
        'description': (
            'Review infrastructure governance posture, beginning with Kubernetes TLS '
            'certificate inventory and lifecycle controls.'
        ),
        'icon': 'shield-check',
        'asset': 'Cross-domain',
        'targets': (
            ('governance.view', 'governance.overview'),
            ('tls_certificates.view', 'governance.tls_certificates'),
        ),
    },
    {
        'title': 'Reports',
        'label': 'Management output',
        'description': (
            'Open operational reports, generated artifacts, templates, schedules, '
            'and storage workflows available to your role.'
        ),
        'icon': 'file-text',
        'asset': 'Cross-domain',
        'targets': (
            ('reports.view', 'reports.overview'),
            ('reports.generate', 'reports.generate_report'),
            ('reports.manage_templates', 'reports.report_templates'),
            ('reports.manage_schedules', 'reports.schedules'),
            ('reports.manage_storage', 'reports.storage'),
        ),
    },
    {
        'title': 'Access Management',
        'label': 'Administration',
        'description': (
            'Manage users, roles, permissions, login activity, or operational audit '
            'records according to assigned authority.'
        ),
        'icon': 'users-round',
        'asset': 'Platform',
        'targets': (
            ('users.view', 'settings.users'),
            ('roles.view', 'settings.roles'),
            ('settings.view_login_activity', 'settings.login_activity'),
            ('settings.view_operational_activity', 'notifications.activity_log'),
        ),
    },
    {
        'title': 'Account & Settings',
        'label': 'Personal workspace',
        'description': (
            'Manage your account and time preferences; elevated roles can also '
            'configure integrations and system settings.'
        ),
        'icon': 'settings-2',
        'asset': 'Platform',
        'targets': ((None, 'settings.account'),),
    },
)


def build_welcome_shortcuts() -> list[dict[str, str]]:
    shortcuts: list[dict[str, str]] = []

    for definition in WELCOME_SHORTCUT_DEFINITIONS:
        resolved_endpoint: str | None = None
        for permission_key, endpoint in definition['targets']:
            if permission_key is None or current_user.has_permission(permission_key):
                resolved_endpoint = endpoint
                break

        if resolved_endpoint is None:
            continue

        shortcuts.append(
            {
                'title': definition['title'],
                'label': definition['label'],
                'description': definition['description'],
                'icon': definition['icon'],
                'asset': definition['asset'],
                'href': url_for(resolved_endpoint),
            }
        )

    return shortcuts
