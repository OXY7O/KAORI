from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import url_for


@dataclass(frozen=True)
class WorkspaceTabDefinition:
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
    tabs: tuple[WorkspaceTabDefinition, ...]


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
    'tls_certificates.sync',
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
        tabs=(
            WorkspaceTabDefinition(
                'overview', 'Overview', 'layout-dashboard', 'kubernetes_dashboard.index', ('dashboard.view',)
            ),
            WorkspaceTabDefinition('inventory', 'Inventory', 'boxes', 'inventory.overview', ('inventory.view',)),
            WorkspaceTabDefinition(
                'operations',
                'Operations',
                'wrench',
                'kubernetes_operations.secret_management',
                _KUBERNETES_OPERATION_PERMISSIONS,
            ),
            WorkspaceTabDefinition(
                'governance', 'Governance', 'shield-check', 'governance.overview', _KUBERNETES_GOVERNANCE_PERMISSIONS
            ),
            WorkspaceTabDefinition(
                'tenant', 'Tenant', 'building-2', 'tenant.index', ('tenant.view', 'tenant.manage')
            ),
            WorkspaceTabDefinition('analytics', 'Analytics', 'chart-column', 'analytics.overview', ('analytics.view',)),
        ),
    ),
    WorkspaceDefinition(
        key='object_storage',
        label='Object Storage',
        icon='database',
        section='Infrastructure',
        tabs=(
            WorkspaceTabDefinition(
                'overview', 'Overview', 'layout-dashboard', 'object_storage_dashboard.index', ('dashboard.view',)
            ),
            WorkspaceTabDefinition(
                'inventory',
                'Inventory',
                'database',
                'object_storage_inventory.overview',
                ('object_storage_inventory.view',),
            ),
            WorkspaceTabDefinition(
                'analytics',
                'Analytics',
                'chart-column',
                'analytics.object_storage_overview',
                ('object_storage_analytics.view',),
            ),
        ),
    ),
    WorkspaceDefinition(
        key='intelligence',
        label='Intelligence',
        icon='brain-circuit',
        section='Insights',
        tabs=(
            WorkspaceTabDefinition('overview', 'Overview', 'layout-dashboard', 'intelligence.index', ('intelligence.view',)),
            WorkspaceTabDefinition(
                'recommendations', 'Recommendations', 'sparkles', 'intelligence.recommendations', ('intelligence.view',)
            ),
            WorkspaceTabDefinition(
                'alert_intelligence',
                'Alert Intelligence',
                'triangle-alert',
                'alert_intelligence.index',
                ('intelligence.view',),
            ),
            WorkspaceTabDefinition('catalog', 'Rule Catalog', 'list-checks', 'intelligence.catalog', ('intelligence.view',)),
            WorkspaceTabDefinition(
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
        tabs=(
            WorkspaceTabDefinition('overview', 'Overview', 'layout-dashboard', 'reports.overview', ('reports.view',)),
            WorkspaceTabDefinition('generate', 'Generate', 'file-plus-2', 'reports.generate_report', ('reports.generate',)),
            WorkspaceTabDefinition('generated', 'Generated', 'files', 'reports.generated_reports', ('reports.view',)),
            WorkspaceTabDefinition(
                'templates', 'Templates', 'layout-template', 'reports.report_templates', ('reports.manage_templates',)
            ),
            WorkspaceTabDefinition('storage', 'Storage', 'hard-drive', 'reports.storage', ('reports.manage_storage',)),
            WorkspaceTabDefinition(
                'schedules', 'Schedules', 'calendar-clock', 'reports.schedules', ('reports.manage_schedules',)
            ),
        ),
    ),
    WorkspaceDefinition(
        key='operations_center',
        label='Operations Center',
        icon='workflow',
        section='Platform',
        tabs=(
            WorkspaceTabDefinition(
                'overview',
                'Overview',
                'layout-dashboard',
                'platform_operations.overview.index',
                _OPERATIONS_CENTER_PERMISSIONS,
            ),
            WorkspaceTabDefinition('jobs', 'Jobs', 'list-checks', 'jobs.executions', ('jobs.view',)),
            WorkspaceTabDefinition(
                'data_lifecycle',
                'Data Lifecycle',
                'archive-restore',
                'platform_operations.data_lifecycle.index',
                ('platform_operations.view_data_lifecycle',),
            ),
            WorkspaceTabDefinition(
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
        tabs=(
            WorkspaceTabDefinition('overview', 'Overview', 'layout-grid', 'integrations.overview', ('integrations.manage',)),
            WorkspaceTabDefinition(
                'orchestration', 'Orchestration', 'workflow', 'integrations.orchestration', ('integrations.manage',)
            ),
            WorkspaceTabDefinition(
                'observability', 'Observability', 'activity', 'integrations.observability', ('integrations.manage',)
            ),
            WorkspaceTabDefinition('storage', 'Storage', 'database', 'integrations.storage', ('integrations.manage',)),
            WorkspaceTabDefinition(
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
        tabs=(
            WorkspaceTabDefinition('overview', 'Overview', 'layout-dashboard', 'access.overview.index', _ACCESS_PERMISSIONS),
            WorkspaceTabDefinition('users', 'Users', 'users-round', 'users.index', ('users.view',)),
            WorkspaceTabDefinition(
                'identity_providers',
                'Identity Providers',
                'fingerprint',
                'identity_providers.index',
                ('identity_providers.view',),
            ),
            WorkspaceTabDefinition('roles', 'Roles', 'badge-check', 'access.roles.index', ('roles.view',)),
            WorkspaceTabDefinition('permissions', 'Permissions', 'key-round', 'access.permissions.index', ('roles.view',)),
            WorkspaceTabDefinition(
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
        tabs=(
            WorkspaceTabDefinition('general', 'General', 'settings', 'settings.general'),
            WorkspaceTabDefinition('account', 'Account', 'user', 'settings.account'),
        ),
    ),
)

_SECTION_ORDER = ('Main', 'Infrastructure', 'Operations', 'Assurance', 'Insights', 'Platform', 'Administration')


def _has_any_permission(user: Any, permissions: tuple[str, ...]) -> bool:
    if not permissions:
        return True
    return any(user.has_permission(permission) for permission in permissions)


def _visible_tabs(workspace: WorkspaceDefinition, user: Any) -> tuple[WorkspaceTabDefinition, ...]:
    return tuple(tab for tab in workspace.tabs if _has_any_permission(user, tab.permissions))


def _resolved_tab_endpoint(workspace_key: str, tab: WorkspaceTabDefinition, user: Any) -> str:
    if workspace_key == 'kubernetes' and tab.key == 'operations':
        if _has_any_permission(user, _KUBERNETES_CONFIGMAP_PERMISSIONS):
            return 'kubernetes_operations.configmap_management'
        return 'kubernetes_operations.secret_management'

    if workspace_key == 'kubernetes' and tab.key == 'governance':
        if user.has_permission('governance.view'):
            return 'governance.overview'
        return 'governance.tls_certificates'

    return tab.endpoint


def _workspace_key(endpoint: str) -> str | None:
    if endpoint.startswith('analytics.object_storage_'):
        return 'object_storage'
    if endpoint.startswith(('object_storage_dashboard.', 'object_storage_inventory.')):
        return 'object_storage'
    if endpoint.startswith(
        ('kubernetes_dashboard.', 'inventory.', 'kubernetes_operations.', 'governance.', 'tenant.', 'analytics.')
    ):
        return 'kubernetes'
    if endpoint.startswith(('intelligence.', 'alert_intelligence.', 'automation_control.')):
        return 'intelligence'
    if endpoint.startswith('reports.'):
        return 'reports'
    if endpoint.startswith(('jobs.', 'platform_operations.')):
        return 'operations_center'
    if endpoint.startswith(('integrations.', 'notification_channels.', 'metrics.', 'alertmanager.', 'minio.', 'cluster.')):
        return 'integrations'
    if endpoint.startswith(('access.', 'users.', 'identity_providers.')):
        return 'access'
    if endpoint.startswith('settings.'):
        return 'settings'
    return None


def _active_tab_key(workspace_key: str, endpoint: str) -> str:
    if workspace_key == 'kubernetes':
        if endpoint.startswith('kubernetes_dashboard.'):
            return 'overview'
        if endpoint.startswith('inventory.'):
            return 'inventory'
        if endpoint.startswith('kubernetes_operations.'):
            return 'operations'
        if endpoint.startswith('governance.'):
            return 'governance'
        if endpoint.startswith('tenant.'):
            return 'tenant'
        return 'analytics'

    if workspace_key == 'object_storage':
        if endpoint.startswith('object_storage_dashboard.'):
            return 'overview'
        if endpoint.startswith('object_storage_inventory.'):
            return 'inventory'
        return 'analytics'

    if workspace_key == 'intelligence':
        if endpoint.startswith('alert_intelligence.'):
            return 'alert_intelligence'
        if endpoint.startswith('automation_control.'):
            return 'automation_control'
        if endpoint.startswith('intelligence.catalog'):
            return 'catalog'
        if endpoint.startswith('intelligence.recommendation'):
            return 'recommendations'
        return 'overview'

    if workspace_key == 'reports':
        if endpoint.startswith(
            ('reports.generated_', 'reports.download_', 'reports.archive_', 'reports.restore_', 'reports.bulk_archive_')
        ):
            return 'generated'
        if endpoint.startswith(
            (
                'reports.report_templates',
                'reports.create_report_template',
                'reports.update_report_template',
                'reports.delete_report_template',
                'reports.duplicate_',
            )
        ):
            return 'templates'
        if endpoint.startswith('reports.storage'):
            return 'storage'
        if endpoint.startswith(
            (
                'reports.schedules',
                'reports.create_schedule',
                'reports.update_schedule',
                'reports.toggle_schedule',
                'reports.delete_schedule',
                'reports.run_schedule',
            )
        ):
            return 'schedules'
        if endpoint.startswith('reports.generate_report'):
            return 'generate'
        return 'overview'

    if workspace_key == 'operations_center':
        if endpoint.startswith('jobs.'):
            return 'jobs'
        if endpoint.startswith('platform_operations.data_lifecycle.'):
            return 'data_lifecycle'
        if endpoint.startswith('platform_operations.kubernetes.'):
            return 'kubernetes_admin'
        return 'overview'

    if workspace_key == 'integrations':
        if endpoint.startswith('notification_channels.'):
            return 'notifications'
        if endpoint.startswith(('metrics.', 'alertmanager.')) or endpoint == 'integrations.observability':
            return 'observability'
        if endpoint.startswith('minio.') or endpoint == 'integrations.storage':
            return 'storage'
        if endpoint.startswith('cluster.') or endpoint.startswith('integrations.kubernetes') or endpoint == 'integrations.orchestration':
            return 'orchestration'
        return 'overview'

    if workspace_key == 'access':
        if endpoint.startswith('users.'):
            return 'users'
        if endpoint.startswith('identity_providers.'):
            return 'identity_providers'
        if endpoint.startswith('access.roles.'):
            return 'roles'
        if endpoint.startswith('access.permissions.'):
            return 'permissions'
        if endpoint.startswith('access.activity_audit.'):
            return 'activity_audit'
        return 'overview'

    if workspace_key == 'settings':
        return 'account' if endpoint == 'settings.account' else 'general'

    return 'overview'


def build_workspace_navigation(endpoint: str | None, user: Any) -> dict[str, Any] | None:
    if not getattr(user, 'is_authenticated', False):
        return None

    resolved_endpoint = endpoint or ''
    workspace_key = _workspace_key(resolved_endpoint)
    if workspace_key is None:
        return None

    workspace = next(item for item in WORKSPACES if item.key == workspace_key)
    visible_tabs = _visible_tabs(workspace, user)
    if not visible_tabs:
        return None

    active_key = _active_tab_key(workspace_key, resolved_endpoint)
    if active_key not in {tab.key for tab in visible_tabs}:
        active_key = visible_tabs[0].key

    return {
        'key': workspace.key,
        'label': workspace.label,
        'icon': workspace.icon,
        'active_key': active_key,
        'tabs': tuple(
            (tab.key, tab.label, tab.icon, None, url_for(_resolved_tab_endpoint(workspace.key, tab, user)))
            for tab in visible_tabs
        ),
    }


def build_sidebar_navigation(endpoint: str | None, user: Any) -> tuple[dict[str, Any], ...]:
    if not getattr(user, 'is_authenticated', False):
        return ()

    resolved_endpoint = endpoint or ''
    active_workspace = _workspace_key(resolved_endpoint)
    sections: dict[str, list[dict[str, Any]]] = {section: [] for section in _SECTION_ORDER}

    sections['Main'].append(
        {
            'key': 'welcome',
            'label': 'Welcome',
            'icon': 'sparkles',
            'href': url_for('welcome.index'),
            'active': resolved_endpoint == 'welcome.index',
        }
    )

    for workspace in WORKSPACES:
        visible_tabs = _visible_tabs(workspace, user)
        if not visible_tabs:
            continue
        sections[workspace.section].append(
            {
                'key': workspace.key,
                'label': workspace.label,
                'icon': workspace.icon,
                'href': url_for(_resolved_tab_endpoint(workspace.key, visible_tabs[0], user)),
                'active': active_workspace == workspace.key,
            }
        )

    return tuple(
        {'label': section, 'items': tuple(sections[section])}
        for section in _SECTION_ORDER
        if sections[section]
    )
