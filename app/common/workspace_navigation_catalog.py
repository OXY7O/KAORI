from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceCapabilityDefinition:
    key: str
    label: str
    icon: str
    endpoint: str
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkspaceDefinition:
    key: str
    label: str
    icon: str
    section: str
    capabilities: tuple[WorkspaceCapabilityDefinition, ...]


@dataclass(frozen=True)
class CapabilityViewDefinition:
    key: str
    label: str
    icon: str
    endpoint: str
    permissions: tuple[str, ...] = ()


_KUBERNETES_CONFIGMAP_PERMISSIONS = (
    'kubernetes_configmaps.view',
    'kubernetes_configmaps.create',
    'kubernetes_configmaps.update',
    'kubernetes_configmaps.delete',
)

_KUBERNETES_SECRET_PERMISSIONS = (
    'kubernetes_secrets.view',
    'kubernetes_secrets.create',
    'kubernetes_secrets.replace',
    'kubernetes_secrets.delete',
    'kubernetes_secrets.reveal',
    'kubernetes_secrets.approve_reveal',
    'kubernetes_secrets.rotate_tls',
    'kubernetes_secrets.bulk_rotate_tls',
)

_KUBERNETES_OPERATION_PERMISSIONS = _KUBERNETES_CONFIGMAP_PERMISSIONS + _KUBERNETES_SECRET_PERMISSIONS

_KUBERNETES_GOVERNANCE_PERMISSIONS = (
    'governance.view',
    'tls_certificates.view',
)

_OPERATIONS_CENTER_PERMISSIONS = (
    'jobs.view',
    'platform_operations.view_data_lifecycle',
    'kubernetes_secrets.manage_reveal',
)

_ACCESS_PERMISSIONS = (
    'users.view',
    'users.manage',
    'identity_providers.view',
    'roles.view',
    'activity_audit.view',
)

WORKSPACES: tuple[WorkspaceDefinition, ...] = (
    WorkspaceDefinition(
        key='kubernetes',
        label='Kubernetes',
        icon='boxes',
        section='Infrastructure',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview', 'Overview', 'layout-dashboard', 'kubernetes_dashboard.index', ('dashboard.view',)
            ),
            WorkspaceCapabilityDefinition('inventory', 'Inventory', 'boxes', 'inventory.overview', ('inventory.view',)),
            WorkspaceCapabilityDefinition(
                'operations',
                'Operations',
                'wrench',
                'kubernetes_operations.secret_management',
                _KUBERNETES_OPERATION_PERMISSIONS,
            ),
            WorkspaceCapabilityDefinition(
                'governance', 'Governance', 'shield-check', 'governance.overview', _KUBERNETES_GOVERNANCE_PERMISSIONS
            ),
            WorkspaceCapabilityDefinition(
                'tenant', 'Tenant', 'building-2', 'tenant.index', ('tenant.view', 'tenant.manage')
            ),
            WorkspaceCapabilityDefinition(
                'analytics',
                'Analytics',
                'chart-column',
                'analytics.overview',
                ('analytics.view',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='object_storage',
        label='Object Storage',
        icon='database',
        section='Infrastructure',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview', 'Overview', 'layout-dashboard', 'object_storage_dashboard.index', ('dashboard.view',)
            ),
            WorkspaceCapabilityDefinition(
                'inventory',
                'Inventory',
                'database',
                'object_storage_inventory.overview',
                ('object_storage_inventory.view',),
            ),
            WorkspaceCapabilityDefinition(
                'analytics',
                'Analytics',
                'chart-column',
                'analytics.object_storage_overview',
                ('object_storage_analytics.view',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='artifact_registry',
        label='Artifact Registry',
        icon='package',
        section='Infrastructure',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview',
                'Overview',
                'layout-dashboard',
                'artifact_registry.overview',
                ('artifact_registry.view',),
            ),
            WorkspaceCapabilityDefinition(
                'inventory',
                'Inventory',
                'boxes',
                'artifact_registry.inventory',
                ('artifact_registry.view',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='intelligence',
        label='Intelligence',
        icon='brain-circuit',
        section='Insights',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview',
                'Overview',
                'layout-dashboard',
                'intelligence.index',
                ('intelligence.view',),
            ),
            WorkspaceCapabilityDefinition(
                'recommendations', 'Recommendations', 'sparkles', 'intelligence.recommendations', ('intelligence.view',)
            ),
            WorkspaceCapabilityDefinition(
                'alert_intelligence',
                'Alert Intelligence',
                'triangle-alert',
                'alert_intelligence.index',
                ('intelligence.view',),
            ),
            WorkspaceCapabilityDefinition(
                'catalog',
                'Rule Catalog',
                'list-checks',
                'intelligence.catalog',
                ('intelligence.view',),
            ),
            WorkspaceCapabilityDefinition(
                'automation_control',
                'Automation Control',
                'workflow',
                'automation_control.index',
                ('intelligence.view',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='reports',
        label='Reports',
        icon='file-text',
        section='Insights',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview',
                'Overview',
                'layout-dashboard',
                'reports.overview',
                ('reports.view',),
            ),
            WorkspaceCapabilityDefinition(
                'generate',
                'Generate',
                'file-plus-2',
                'reports.generate_report',
                ('reports.generate',),
            ),
            WorkspaceCapabilityDefinition(
                'generated',
                'Generated',
                'files',
                'reports.generated_reports',
                ('reports.view',),
            ),
            WorkspaceCapabilityDefinition(
                'templates', 'Templates', 'layout-template', 'reports.report_templates', ('reports.manage_templates',)
            ),
            WorkspaceCapabilityDefinition(
                'storage',
                'Storage',
                'hard-drive',
                'reports.storage',
                ('reports.manage_storage',),
            ),
            WorkspaceCapabilityDefinition(
                'schedules', 'Schedules', 'calendar-clock', 'reports.schedules', ('reports.manage_schedules',)
            ),
        ),
    ),
    WorkspaceDefinition(
        key='operations_center',
        label='Operations Center',
        icon='workflow',
        section='Platform',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview',
                'Overview',
                'layout-dashboard',
                'platform_operations.overview.index',
                _OPERATIONS_CENTER_PERMISSIONS,
            ),
            WorkspaceCapabilityDefinition('jobs', 'Jobs', 'list-checks', 'jobs.executions', ('jobs.view',)),
            WorkspaceCapabilityDefinition(
                'data_lifecycle',
                'Data Lifecycle',
                'archive-restore',
                'platform_operations.data_lifecycle.index',
                ('platform_operations.view_data_lifecycle',),
            ),
            WorkspaceCapabilityDefinition(
                'kubernetes_admin',
                'Kubernetes Admin',
                'server-cog',
                'platform_operations.kubernetes.index',
                ('kubernetes_secrets.manage_reveal',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='integrations',
        label='Integrations',
        icon='blocks',
        section='Platform',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview',
                'Overview',
                'layout-grid',
                'integrations.overview',
                ('integrations.manage',),
            ),
            WorkspaceCapabilityDefinition(
                'orchestration', 'Orchestration', 'workflow', 'integrations.orchestration', ('integrations.manage',)
            ),
            WorkspaceCapabilityDefinition(
                'observability', 'Observability', 'activity', 'integrations.observability', ('integrations.manage',)
            ),
            WorkspaceCapabilityDefinition(
                'storage',
                'Storage',
                'database',
                'integrations.storage',
                ('integrations.manage',),
            ),
            WorkspaceCapabilityDefinition(
                'registry',
                'Registry',
                'package',
                'integrations.registry',
                ('integrations.manage',),
            ),
            WorkspaceCapabilityDefinition(
                'notifications',
                'Notification Channels',
                'send',
                'notification_channels.index',
                ('integrations.manage',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='access',
        label='Access',
        icon='shield-check',
        section='Administration',
        capabilities=(
            WorkspaceCapabilityDefinition(
                'overview',
                'Overview',
                'layout-dashboard',
                'access.overview.index',
                _ACCESS_PERMISSIONS,
            ),
            WorkspaceCapabilityDefinition('users', 'Users', 'users-round', 'users.index', ('users.view',)),
            WorkspaceCapabilityDefinition(
                'identity_providers',
                'Identity Providers',
                'fingerprint',
                'identity_providers.index',
                ('identity_providers.view',),
            ),
            WorkspaceCapabilityDefinition('roles', 'Roles', 'badge-check', 'access.roles.index', ('roles.view',)),
            WorkspaceCapabilityDefinition(
                'permissions',
                'Permissions',
                'key-round',
                'access.permissions.index',
                ('roles.view',),
            ),
            WorkspaceCapabilityDefinition(
                'activity_audit',
                'Activity Audit',
                'history',
                'access.activity_audit.index',
                ('activity_audit.view',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='settings',
        label='Settings',
        icon='settings',
        section='Administration',
        capabilities=(
            WorkspaceCapabilityDefinition('general', 'General', 'settings', 'settings.general'),
            WorkspaceCapabilityDefinition('account', 'Account', 'user', 'settings.account'),
        ),
    ),
)

_SECTION_ORDER = ('Main', 'Infrastructure', 'Operations', 'Assurance', 'Insights', 'Platform', 'Administration')

_WORKSPACE_CONTEXT_KEYS: dict[str, tuple[str, ...]] = {
    'kubernetes': ('cluster_id',),
    'object_storage': ('system_id',),
}

_CAPABILITY_CONTEXT_KEYS: dict[str, tuple[str, ...]] = {
    'kubernetes_inventory': ('cluster_id',),
    'kubernetes_operations': ('cluster_id', 'namespace'),
    'kubernetes_governance': ('cluster_id',),
    'kubernetes_tenant': ('cluster_id',),
    'kubernetes_analytics': ('cluster_id', 'time_range'),
    'object_storage_inventory': ('system_id',),
    'object_storage_analytics': ('system_id', 'time_range'),
}


_CAPABILITY_VIEWS: dict[str, tuple[CapabilityViewDefinition, ...]] = {
    'kubernetes_inventory': (
        CapabilityViewDefinition('overview', 'Overview', 'layout-grid', 'inventory.overview', ('inventory.view',)),
        CapabilityViewDefinition('topology', 'Topology', 'waypoints', 'inventory.topology', ('inventory.view',)),
        CapabilityViewDefinition('nodes', 'Nodes', 'server', 'inventory.nodes', ('inventory.view',)),
        CapabilityViewDefinition('namespaces', 'Namespaces', 'folders', 'inventory.namespaces', ('inventory.view',)),
        CapabilityViewDefinition('workloads', 'Workloads', 'boxes', 'inventory.workloads', ('inventory.view',)),
        CapabilityViewDefinition('pods', 'Pods', 'box', 'inventory.pods', ('inventory.view',)),
        CapabilityViewDefinition('services', 'Services', 'network', 'inventory.services', ('inventory.view',)),
        CapabilityViewDefinition('ingresses', 'Ingresses', 'route', 'inventory.ingresses', ('inventory.view',)),
        CapabilityViewDefinition('storage', 'Storage', 'hard-drive', 'inventory.storage', ('inventory.view',)),
        CapabilityViewDefinition(
            'configuration', 'Configuration', 'file-key-2', 'inventory.configuration', ('inventory.view',)
        ),
    ),
    'kubernetes_operations': (
        CapabilityViewDefinition(
            'configmaps',
            'ConfigMaps',
            'file-cog',
            'kubernetes_operations.configmap_management',
            _KUBERNETES_CONFIGMAP_PERMISSIONS,
        ),
        CapabilityViewDefinition(
            'secrets',
            'Secrets',
            'key-round',
            'kubernetes_operations.secret_management',
            _KUBERNETES_SECRET_PERMISSIONS,
        ),
    ),
    'kubernetes_governance': (
        CapabilityViewDefinition(
            'overview',
            'Overview',
            'layout-dashboard',
            'governance.overview',
            ('governance.view',),
        ),
        CapabilityViewDefinition(
            'tls_certificates',
            'TLS Certificates',
            'badge-check',
            'governance.tls_certificates',
            ('tls_certificates.view',),
        ),
    ),
    'kubernetes_tenant': (
        CapabilityViewDefinition(
            'overview',
            'Overview',
            'layout-dashboard',
            'tenant.index',
            ('tenant.view', 'tenant.manage'),
        ),
        CapabilityViewDefinition(
            'tenants',
            'Tenants',
            'building-2',
            'tenant.tenants',
            ('tenant.view', 'tenant.manage'),
        ),
        CapabilityViewDefinition(
            'resource_profiles',
            'Resource Profiles',
            'layers-3',
            'tenant.resource_profiles',
            ('tenant.view', 'tenant.manage'),
        ),
        CapabilityViewDefinition(
            'namespace_provisioning',
            'Namespace Provisioning',
            'folder-plus',
            'tenant.namespace_provisioning',
            ('tenant.view', 'tenant.manage'),
        ),
        CapabilityViewDefinition(
            'operations', 'Operations', 'activity', 'tenant.operations', ('tenant.view', 'tenant.manage')
        ),
    ),
    'kubernetes_analytics': (
        CapabilityViewDefinition('overview', 'Overview', 'layout-dashboard', 'analytics.overview', ('analytics.view',)),
        CapabilityViewDefinition('utilization', 'Usage', 'activity', 'analytics.utilization', ('analytics.view',)),
        CapabilityViewDefinition('capacity', 'Capacity', 'gauge', 'analytics.capacity', ('analytics.view',)),
        CapabilityViewDefinition('workloads', 'Workloads', 'boxes', 'analytics.workload', ('analytics.view',)),
        CapabilityViewDefinition('storage', 'Storage', 'hard-drive', 'analytics.storage', ('analytics.view',)),
        CapabilityViewDefinition('consumers', 'Consumers', 'users', 'analytics.top_consumers', ('analytics.view',)),
        CapabilityViewDefinition('forecast', 'Forecast', 'line-chart', 'analytics.forecast', ('analytics.view',)),
        CapabilityViewDefinition(
            'alerts',
            'Alerts & Anomalies',
            'triangle-alert',
            'analytics.alerts',
            ('analytics.view',),
        ),
    ),
    'object_storage_inventory': (
        CapabilityViewDefinition(
            'overview',
            'Overview',
            'layout-grid',
            'object_storage_inventory.overview',
            ('object_storage_inventory.view',),
        ),
        CapabilityViewDefinition(
            'systems',
            'Systems',
            'server',
            'object_storage_inventory.systems',
            ('object_storage_inventory.view',),
        ),
        CapabilityViewDefinition(
            'buckets',
            'Buckets & Containers',
            'container',
            'object_storage_inventory.buckets',
            ('object_storage_inventory.view',),
        ),
    ),
    'object_storage_analytics': (
        CapabilityViewDefinition(
            'overview',
            'Overview',
            'layout-dashboard',
            'analytics.object_storage_overview',
            ('object_storage_analytics.view',),
        ),
        CapabilityViewDefinition(
            'capacity',
            'Capacity & Usage',
            'database',
            'analytics.object_storage_capacity',
            ('object_storage_analytics.view',),
        ),
        CapabilityViewDefinition(
            'performance',
            'Performance',
            'activity',
            'analytics.object_storage_performance',
            ('object_storage_analytics.view',),
        ),
        CapabilityViewDefinition(
            'forecast',
            'Forecast',
            'line-chart',
            'analytics.object_storage_forecast',
            ('object_storage_analytics.view',),
        ),
        CapabilityViewDefinition(
            'consumers',
            'Top Consumers',
            'users',
            'analytics.object_storage_top_consumers',
            ('object_storage_analytics.view',),
        ),
        CapabilityViewDefinition(
            'alerts',
            'Alerts & Anomalies',
            'triangle-alert',
            'analytics.object_storage_alerts',
            ('object_storage_analytics.view',),
        ),
    ),
}
