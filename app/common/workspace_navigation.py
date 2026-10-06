from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from flask import url_for

from app.common.workspace_navigation_catalog import (
    _CAPABILITY_CONTEXT_KEYS,
    _CAPABILITY_VIEWS,
    _KUBERNETES_CONFIGMAP_PERMISSIONS,
    _SECTION_ORDER,
    _WORKSPACE_CONTEXT_KEYS,
    WORKSPACES,
    WorkspaceCapabilityDefinition,
    WorkspaceDefinition,
)


def _capability_key(endpoint: str) -> str | None:
    if endpoint.startswith('inventory.'):
        return 'kubernetes_inventory'
    if endpoint.startswith('kubernetes_operations.'):
        return 'kubernetes_operations'
    if endpoint.startswith('governance.'):
        return 'kubernetes_governance'
    if endpoint.startswith('tenant.'):
        return 'kubernetes_tenant'
    if endpoint.startswith('analytics.object_storage_'):
        return 'object_storage_analytics'
    if endpoint.startswith('analytics.'):
        return 'kubernetes_analytics'
    if endpoint.startswith('object_storage_inventory.'):
        return 'object_storage_inventory'
    if endpoint.startswith('artifact_registry.inventory'):
        return 'artifact_registry_inventory'
    if endpoint.startswith('artifact_registry.security'):
        return 'artifact_registry_security'
    return None


def _capability_label(capability_key: str) -> str:
    return {
        'kubernetes_inventory': 'Inventory',
        'kubernetes_operations': 'Operations',
        'kubernetes_governance': 'Governance',
        'kubernetes_tenant': 'Tenant',
        'kubernetes_analytics': 'Analytics',
        'object_storage_inventory': 'Inventory',
        'object_storage_analytics': 'Analytics',
        'artifact_registry_inventory': 'Inventory',
        'artifact_registry_security': 'Security',
    }[capability_key]


_CAPABILITY_ACTIVE_EXACT: dict[str, dict[str, str]] = {
    'kubernetes_inventory': {
        'inventory.nodes': 'nodes',
        'inventory.node_details': 'nodes',
        'inventory.namespaces': 'namespaces',
        'inventory.namespace_details': 'namespaces',
        'inventory.workloads': 'workloads',
        'inventory.workload_details': 'workloads',
        'inventory.pods': 'pods',
        'inventory.pod_details': 'pods',
        'inventory.services': 'services',
        'inventory.service_details': 'services',
        'inventory.ingresses': 'ingresses',
        'inventory.ingress_details': 'ingresses',
        'inventory.storage': 'storage',
        'inventory.storage_details': 'storage',
        'inventory.configuration': 'configuration',
        'inventory.configuration_details': 'configuration',
    },
    'kubernetes_operations': {
        'kubernetes_operations.create_configmap': 'configmaps',
        'kubernetes_operations.update_configmap': 'configmaps',
        'kubernetes_operations.delete_configmap': 'configmaps',
    },
    'kubernetes_tenant': {
        'tenant.tenants': 'tenants',
        'tenant.resource_profiles': 'resource_profiles',
        'tenant.namespace_provisioning': 'namespace_provisioning',
        'tenant.operations': 'operations',
    },
    'kubernetes_analytics': {
        'analytics.capacity': 'capacity',
        'analytics.forecast': 'forecast',
    },
    'object_storage_inventory': {
        'object_storage_inventory.systems': 'systems',
        'object_storage_inventory.system_details': 'systems',
        'object_storage_inventory.buckets': 'buckets',
        'object_storage_inventory.bucket_details': 'buckets',
    },
    'artifact_registry_inventory': {
        'artifact_registry.inventory_projects': 'projects',
        'artifact_registry.inventory_repositories': 'repositories',
        'artifact_registry.inventory_artifacts': 'artifacts',
    },
    'artifact_registry_security': {
        'artifact_registry.security': 'vulnerabilities',
        'artifact_registry.security_supply_chain': 'supply_chain',
    },
    'object_storage_analytics': {
        'analytics.object_storage_capacity': 'capacity',
        'analytics.object_storage_performance': 'performance',
        'analytics.object_storage_forecast': 'forecast',
        'analytics.object_storage_top_consumers': 'consumers',
    },
}

_CAPABILITY_ACTIVE_PREFIXES: dict[str, tuple[tuple[str, str], ...]] = {
    'kubernetes_inventory': (('inventory.topology', 'topology'),),
    'kubernetes_operations': (('kubernetes_operations.configmap', 'configmaps'),),
    'kubernetes_governance': (('governance.tls_certificates', 'tls_certificates'),),
    'kubernetes_analytics': (
        ('analytics.utilization', 'utilization'),
        ('analytics.workload', 'workloads'),
        ('analytics.storage', 'storage'),
        ('analytics.top_consumers', 'consumers'),
        ('analytics.alerts', 'alerts'),
    ),
    'object_storage_analytics': (('analytics.object_storage_alert', 'alerts'),),
}

_CAPABILITY_ACTIVE_DEFAULTS = {
    'kubernetes_operations': 'secrets',
    'artifact_registry_security': 'vulnerabilities',
}


def _capability_active_key(capability_key: str, endpoint: str) -> str:
    exact = _CAPABILITY_ACTIVE_EXACT.get(capability_key, {})
    if endpoint in exact:
        return exact[endpoint]

    for prefix, key in _CAPABILITY_ACTIVE_PREFIXES.get(capability_key, ()):
        if endpoint.startswith(prefix):
            return key

    return _CAPABILITY_ACTIVE_DEFAULTS.get(capability_key, 'overview')


def _preserved_context(
    query_args: Mapping[str, Any] | None,
    keys: tuple[str, ...],
) -> dict[str, str]:
    if query_args is None:
        return {}

    context: dict[str, str] = {}
    for key in keys:
        value = str(query_args.get(key) or '').strip()
        if value:
            context[key] = value
    return context


def build_capability_navigation(
    endpoint: str | None,
    user: Any,
    query_args: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not getattr(user, 'is_authenticated', False):
        return None

    resolved_endpoint = endpoint or ''
    capability_key = _capability_key(resolved_endpoint)
    if capability_key is None:
        return None

    visible_views = tuple(
        view for view in _CAPABILITY_VIEWS[capability_key] if _has_any_permission(user, view.permissions)
    )
    if len(visible_views) < 2:
        return None

    active_key = _capability_active_key(capability_key, resolved_endpoint)
    if active_key not in {view.key for view in visible_views}:
        active_key = visible_views[0].key

    return {
        'key': capability_key,
        'label': _capability_label(capability_key),
        'active_key': active_key,
        'tabs': tuple(
            (
                view.key,
                view.label,
                view.icon,
                None,
                url_for(
                    view.endpoint,
                    **cast(
                        dict[str, Any],
                        _preserved_context(query_args, _CAPABILITY_CONTEXT_KEYS.get(capability_key, ())),
                    ),
                ),
            )
            for view in visible_views
        ),
    }


def _has_any_permission(user: Any, permissions: tuple[str, ...]) -> bool:
    if not permissions:
        return True
    return any(user.has_permission(permission) for permission in permissions)


def _visible_capabilities(workspace: WorkspaceDefinition, user: Any) -> tuple[WorkspaceCapabilityDefinition, ...]:
    return tuple(tab for tab in workspace.capabilities if _has_any_permission(user, tab.permissions))


def _resolved_capability_endpoint(workspace_key: str, tab: WorkspaceCapabilityDefinition, user: Any) -> str:
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
    if endpoint.startswith('artifact_registry.'):
        return 'artifact_registry'
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
    if endpoint.startswith(
        ('integrations.', 'notification_channels.', 'metrics.', 'alertmanager.', 'minio.', 'harbor.', 'cluster.')
    ):
        return 'integrations'
    if endpoint.startswith(('access.', 'users.', 'identity_providers.')):
        return 'access'
    if endpoint.startswith('settings.'):
        return 'settings'
    return None


_WORKSPACE_ACTIVE_EXACT: dict[str, dict[str, str]] = {
    'settings': {'settings.account': 'account'},
    'integrations': {
        'integrations.observability': 'observability',
        'integrations.storage': 'storage',
        'integrations.orchestration': 'orchestration',
        'integrations.registry': 'registry',
    },
}

_WORKSPACE_ACTIVE_PREFIXES: dict[str, tuple[tuple[str, str], ...]] = {
    'kubernetes': (
        ('kubernetes_dashboard.', 'overview'),
        ('inventory.', 'inventory'),
        ('kubernetes_operations.', 'operations'),
        ('governance.', 'governance'),
        ('tenant.', 'tenant'),
    ),
    'object_storage': (
        ('object_storage_dashboard.', 'overview'),
        ('object_storage_inventory.', 'inventory'),
    ),
    'artifact_registry': (
        ('artifact_registry.inventory', 'inventory'),
        ('artifact_registry.security', 'security'),
        ('artifact_registry.runtime', 'runtime'),
        ('artifact_registry.governance', 'governance'),
        ('artifact_registry.analytics', 'analytics'),
    ),
    'intelligence': (
        ('alert_intelligence.', 'alert_intelligence'),
        ('automation_control.', 'automation_control'),
        ('intelligence.catalog', 'catalog'),
        ('intelligence.recommendation', 'recommendations'),
    ),
    'reports': (
        ('reports.generated_', 'generated'),
        ('reports.download_', 'generated'),
        ('reports.archive_', 'generated'),
        ('reports.restore_', 'generated'),
        ('reports.bulk_archive_', 'generated'),
        ('reports.report_templates', 'templates'),
        ('reports.create_report_template', 'templates'),
        ('reports.update_report_template', 'templates'),
        ('reports.delete_report_template', 'templates'),
        ('reports.duplicate_', 'templates'),
        ('reports.storage', 'storage'),
        ('reports.schedules', 'schedules'),
        ('reports.create_schedule', 'schedules'),
        ('reports.update_schedule', 'schedules'),
        ('reports.toggle_schedule', 'schedules'),
        ('reports.delete_schedule', 'schedules'),
        ('reports.run_schedule', 'schedules'),
        ('reports.generate_report', 'generate'),
    ),
    'operations_center': (
        ('jobs.', 'jobs'),
        ('platform_operations.data_lifecycle.', 'data_lifecycle'),
        ('platform_operations.kubernetes.', 'kubernetes_admin'),
    ),
    'integrations': (
        ('notification_channels.', 'notifications'),
        ('metrics.', 'observability'),
        ('alertmanager.', 'observability'),
        ('minio.', 'storage'),
        ('harbor.', 'registry'),
        ('cluster.', 'orchestration'),
        ('integrations.kubernetes', 'orchestration'),
    ),
    'access': (
        ('users.', 'users'),
        ('identity_providers.', 'identity_providers'),
        ('access.roles.', 'roles'),
        ('access.permissions.', 'permissions'),
        ('access.activity_audit.', 'activity_audit'),
    ),
}

_WORKSPACE_ACTIVE_DEFAULTS = {
    'kubernetes': 'analytics',
    'object_storage': 'analytics',
    'artifact_registry': 'overview',
    'settings': 'general',
}


def _active_capability_key(workspace_key: str, endpoint: str) -> str:
    exact = _WORKSPACE_ACTIVE_EXACT.get(workspace_key, {})
    if endpoint in exact:
        return exact[endpoint]

    for prefix, key in _WORKSPACE_ACTIVE_PREFIXES.get(workspace_key, ()):
        if endpoint.startswith(prefix):
            return key

    return _WORKSPACE_ACTIVE_DEFAULTS.get(workspace_key, 'overview')


def build_sidebar_navigation(
    endpoint: str | None,
    user: Any,
    query_args: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
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
            'children': (),
        }
    )

    for workspace in WORKSPACES:
        visible_capabilities = _visible_capabilities(workspace, user)
        if not visible_capabilities:
            continue

        active_capability = (
            _active_capability_key(workspace.key, resolved_endpoint) if active_workspace == workspace.key else None
        )
        context = _preserved_context(
            query_args,
            _WORKSPACE_CONTEXT_KEYS.get(workspace.key, ()),
        )
        children = tuple(
            {
                'key': capability.key,
                'label': capability.label,
                'icon': capability.icon,
                'href': url_for(
                    _resolved_capability_endpoint(workspace.key, capability, user),
                    **cast(dict[str, Any], context),
                ),
                'active': (active_workspace == workspace.key and capability.key == active_capability),
            }
            for capability in visible_capabilities
        )

        sections[workspace.section].append(
            {
                'key': workspace.key,
                'label': workspace.label,
                'icon': workspace.icon,
                'active': active_workspace == workspace.key,
                'children': children,
            }
        )

    return tuple(
        {'label': section, 'items': tuple(sections[section])} for section in _SECTION_ORDER if sections[section]
    )
