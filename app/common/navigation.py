"""Canonical navigation context for the KAORI topbar breadcrumb.

The first breadcrumb item after KAORI must match the visible main-menu label in
KAORI's sidebar. Child labels describe the selected submenu or workflow page.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class BreadcrumbItem:
    label: str
    icon: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {'label': self.label, 'icon': self.icon}


_ENDPOINT_LABELS: dict[str, str] = {
    # Inventory
    'inventory.overview': 'Overview',
    'inventory.topology': 'Topology',
    'inventory.nodes': 'Nodes',
    'inventory.namespaces': 'Namespaces',
    'inventory.workloads': 'Workloads',
    'inventory.pods': 'Pods',
    'inventory.services': 'Services',
    'inventory.ingresses': 'Ingresses',
    'inventory.storage': 'Storage',
    'inventory.configuration': 'Configuration',
    # Object Storage Inventory
    'object_storage_inventory.overview': 'Overview',
    'object_storage_inventory.systems': 'Systems',
    'object_storage_inventory.system_details': 'System Details',
    'object_storage_inventory.buckets': 'Buckets',
    'object_storage_inventory.bucket_details': 'Bucket Details',
    # Analytics
    'analytics.overview': 'Overview',
    'analytics.utilization': 'Resource Utilization',
    'analytics.capacity': 'Capacity Analysis',
    'analytics.storage': 'Storage Analysis',
    'analytics.workload': 'Workload Analysis',
    'analytics.forecast': 'Resource Forecast',
    'analytics.top_consumers': 'Top Consumers',
    'analytics.alerts': 'Alerts & Anomalies',
    # Object Storage Analytics
    'analytics.object_storage_overview': 'Overview',
    'analytics.object_storage_capacity': 'Capacity & Usage',
    'analytics.object_storage_performance': 'Performance',
    'analytics.object_storage_forecast': 'Forecast',
    'analytics.object_storage_top_consumers': 'Top Consumers',
    'analytics.object_storage_alerts': 'Alerts & Anomalies',
    # Intelligence
    'intelligence.index': 'Recommendations',
    'intelligence.recommendations': 'Recommendations',
    'intelligence.alert_intelligence': 'Alert Intelligence',
    'intelligence.catalog': 'Catalog',
    'automation_control.index': 'Automation Control',
    # Reports
    'reports.overview': 'Overview',
    'reports.generate_report': 'Generate',
    'reports.generated_reports': 'Generated',
    'reports.report_templates': 'Templates',
    'reports.schedules': 'Schedules',
    'reports.storage': 'Storage',
    # Kubernetes operations and governance
    'kubernetes_operations.configmap_management': 'ConfigMap Management',
    'kubernetes_operations.secret_management': 'Secret Management',
    'governance.overview': 'Overview',
    'governance.tls_certificates': 'TLS Certificates',
    # Platform operations
    'jobs.executions': 'Executions',
    'jobs.configuration': 'Job Configuration',
    'platform_operations.overview.index': 'Overview',
    'platform_operations.data_lifecycle.index': 'Data Lifecycle',
    'platform_operations.kubernetes.index': 'Kubernetes Administration',
    'platform_operations.kubernetes.secret_reveal.index': 'Secret Reveal',
    # Settings
    'settings.general': 'General',
    'settings.account': 'Account',
    # Access
    'access.overview.index': 'Overview',
    'users.index': 'User Management',
    'users.providers': 'Identity Providers',
    'users.external_identities': 'Directory Provisioning',
    'access.roles.index': 'Roles & Access',
    'access.permissions.index': 'Permission Catalog',
    'notifications.center': 'Notification Center',
    'notifications.activity_log': 'Activity Audit',
}

_WORKFLOW_LABELS: tuple[tuple[str, str], ...] = (
    ('cluster.add_cluster', 'Add Cluster'),
    ('cluster.edit_cluster', 'Edit Cluster'),
    ('prometheus.new_instance', 'Register Connection'),
    ('prometheus.instance_detail', 'Connection Details'),
    ('alertmanager.new_instance', 'Register Connection'),
    ('alertmanager.instance_detail', 'Connection Details'),
    ('minio.new_instance', 'Register Connection'),
    ('minio.instance_detail', 'Connection Details'),
    ('users.create', 'Add User'),
    ('users.edit', 'Edit User'),
    ('users.reset_password', 'Reset Password'),
    ('users.providers', 'Identity Providers'),
    ('users.create_provider', 'Add Provider'),
    ('users.edit_provider', 'Edit Provider'),
    ('users.external_identities', 'External Identities'),
    ('access.roles.create', 'Add Role'),
    ('access.roles.clone', 'Clone Role'),
    ('access.roles.detail', 'Role Details'),
    ('access.roles.edit', 'Edit Role'),
)


def _items(*items: BreadcrumbItem) -> list[dict[str, str | None]]:
    return [item.as_dict() for item in items]


def _leaf(endpoint: str, fallback: str) -> str:
    return _ENDPOINT_LABELS.get(endpoint, fallback)


def _append_workflow(items: list[BreadcrumbItem], endpoint: str) -> list[BreadcrumbItem]:
    workflow = next((label for candidate, label in _WORKFLOW_LABELS if candidate == endpoint), None)
    if workflow and workflow != items[-1].label:
        items.append(BreadcrumbItem(workflow))
    return items


def _deduplicate(items: Iterable[BreadcrumbItem]) -> list[BreadcrumbItem]:
    result: list[BreadcrumbItem] = []
    for item in items:
        if not result or result[-1].label != item.label:
            result.append(item)
    return result


def _analytics_items(endpoint: str) -> list[BreadcrumbItem]:
    if endpoint.startswith('analytics.object_storage_'):
        return [
            BreadcrumbItem('Object Storage Analytics', 'database-zap'),
            BreadcrumbItem(_leaf(endpoint, 'Overview')),
        ]
    return [
        BreadcrumbItem('Kubernetes Analytics', 'bar-chart-3'),
        BreadcrumbItem(_leaf(endpoint, 'Overview')),
    ]


def build_navigation_breadcrumb(
    endpoint: str | None,
    path: str = '',
    *,
    integration_owner: Mapping[str, str] | None = None,
) -> list[dict[str, str | None]]:
    """Return breadcrumb items whose root matches the KAORI sidebar main menu."""

    endpoint = endpoint or ''

    if endpoint == 'welcome.index':
        items = [BreadcrumbItem('Welcome', 'sparkles')]
    elif endpoint.startswith('kubernetes_dashboard.'):
        items = [
            BreadcrumbItem('Dashboards', 'layout-dashboard'),
            BreadcrumbItem('Kubernetes Operations'),
        ]
    elif integration_owner is not None:
        items = [
            BreadcrumbItem('Integrations', 'plug'),
            BreadcrumbItem(integration_owner['domain_label']),
            BreadcrumbItem(integration_owner['provider_label']),
        ]
        items = _append_workflow(items, endpoint)
    elif endpoint.startswith('object_storage_inventory.'):
        items = [
            BreadcrumbItem('Object Storage Inventory', 'database'),
            BreadcrumbItem(_leaf(endpoint, 'Overview')),
        ]
    elif endpoint.startswith('inventory.'):
        items = [
            BreadcrumbItem('Kubernetes Inventory', 'boxes'),
            BreadcrumbItem(_leaf(endpoint, 'Overview')),
        ]
    elif endpoint.startswith('kubernetes_operations.'):
        fallback = 'Secret Management' if 'secret' in endpoint or '/secrets' in path else 'ConfigMap Management'
        items = [
            BreadcrumbItem('Kubernetes Operations', 'terminal-square'),
            BreadcrumbItem(_leaf(endpoint, fallback)),
        ]
    elif endpoint.startswith('governance.'):
        items = [
            BreadcrumbItem('Kubernetes Governance', 'shield-check'),
            BreadcrumbItem(_leaf(endpoint, 'TLS Certificates')),
        ]
    elif endpoint.startswith('analytics.'):
        items = _analytics_items(endpoint)
    elif endpoint.startswith('intelligence.') or endpoint.startswith('automation_control.'):
        items = [
            BreadcrumbItem('Intelligence', 'brain-circuit'),
            BreadcrumbItem(_leaf(endpoint, 'Recommendations')),
        ]
    elif endpoint.startswith('reports.'):
        items = [BreadcrumbItem('Reports', 'file-text'), BreadcrumbItem(_leaf(endpoint, 'Overview'))]
    elif endpoint.startswith('jobs.'):
        items = [
            BreadcrumbItem('Platform Operations', 'workflow'),
            BreadcrumbItem(_leaf(endpoint, 'Jobs & Executions')),
        ]
    elif endpoint.startswith('platform_operations.overview.'):
        items = [
            BreadcrumbItem('Platform Operations', 'workflow'),
            BreadcrumbItem('Operations Center'),
        ]
    elif endpoint.startswith('platform_operations.data_lifecycle.'):
        items = [
            BreadcrumbItem('Platform Operations', 'workflow'),
            BreadcrumbItem('Data Lifecycle'),
        ]
    elif endpoint.startswith('platform_operations.kubernetes.'):
        items = [
            BreadcrumbItem('Platform Operations', 'workflow'),
            BreadcrumbItem('Kubernetes Administration'),
        ]
        if endpoint != 'platform_operations.kubernetes.index':
            items.append(BreadcrumbItem(_leaf(endpoint, 'Secret Reveal')))
    elif endpoint.startswith('integrations.'):
        leaf = {
            'integrations.overview': 'Overview',
            'integrations.orchestration': 'Orchestration',
            'integrations.observability': 'Observability',
            'integrations.storage': 'Storage',
        }.get(endpoint, 'Overview')
        items = [BreadcrumbItem('Integrations', 'plug'), BreadcrumbItem(leaf)]
    elif endpoint.startswith('access.overview.'):
        items = [BreadcrumbItem('Access', 'users-round'), BreadcrumbItem('Overview')]
    elif endpoint in {'users.providers', 'users.create_provider', 'users.edit_provider', 'users.validate_provider'}:
        items = [BreadcrumbItem('Access', 'users-round'), BreadcrumbItem('Identity Providers')]
        items = _append_workflow(items, endpoint)
    elif endpoint in {'users.external_identities', 'users.provision_identity'}:
        items = [
            BreadcrumbItem('Access', 'users-round'),
            BreadcrumbItem('Identity Providers'),
            BreadcrumbItem('Directory Provisioning'),
        ]
    elif endpoint.startswith('users.'):
        items = [BreadcrumbItem('Access', 'users-round'), BreadcrumbItem('User Management')]
        items = _append_workflow(items, endpoint)
    elif endpoint == 'notifications.center':
        items = [BreadcrumbItem('Notification Center', 'bell')]
    elif endpoint.startswith('notifications.'):
        items = [BreadcrumbItem('Access', 'users-round'), BreadcrumbItem(_leaf(endpoint, 'Activity Audit'))]
    elif endpoint.startswith('access.roles.'):
        items = [BreadcrumbItem('Access', 'users-round'), BreadcrumbItem('Roles & Access')]
        items = _append_workflow(items, endpoint)
    elif endpoint.startswith('access.permissions.'):
        items = [BreadcrumbItem('Access', 'users-round'), BreadcrumbItem('Permission Catalog')]
    elif endpoint.startswith('settings.'):
        items = [BreadcrumbItem('Settings', 'settings-2'), BreadcrumbItem(_leaf(endpoint, 'General'))]
    else:
        items = [BreadcrumbItem('KAORI', 'compass')]

    return _items(*_deduplicate(items))
