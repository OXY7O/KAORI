#!/usr/bin/env python3
"""Canonical ownership registry for KAORI release-visible and system surfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseSurface:
    key: str
    title: str
    lock_state: str
    navigation_source: str | None
    navigation_endpoints: tuple[str, ...]
    blueprint_vars: tuple[str, ...]
    verifiers: tuple[str, ...]
    contract_paths: tuple[str, ...]
    notes: str = ''


SURFACES: tuple[ReleaseSurface, ...] = (
    ReleaseSurface(
        key='welcome',
        title='Welcome',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/sidebar.html',
        navigation_endpoints=('welcome.index',),
        blueprint_vars=('welcome_bp',),
        verifiers=('scripts/verify_welcome_final_lock.py',),
        contract_paths=('tests/contracts/welcome',),
    ),
    ReleaseSurface(
        key='dashboard',
        title='Kubernetes Dashboard',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/dashboards_menu.html',
        navigation_endpoints=('kubernetes_dashboard.index',),
        blueprint_vars=('kubernetes_dashboard_bp',),
        verifiers=('scripts/verify_operational_dashboard_standard.py',),
        contract_paths=('tests/contracts/kubernetes/test_operations_dashboard_styling_guide_contract.py',),
    ),
    ReleaseSurface(
        key='inventory',
        title='Kubernetes Inventory',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/inventory_menu.html',
        navigation_endpoints=(
            'inventory.overview',
            'inventory.topology',
            'inventory.nodes',
            'inventory.namespaces',
            'inventory.workloads',
            'inventory.pods',
            'inventory.services',
            'inventory.ingresses',
            'inventory.storage',
            'inventory.configuration',
        ),
        blueprint_vars=('inventory_bp',),
        verifiers=('scripts/verify_inventory_final_lock.py',),
        contract_paths=('tests/contracts/kubernetes/test_inventory_final_release_contract.py',),
    ),
    ReleaseSurface(
        key='object_storage_inventory',
        title='Object Storage Inventory',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/object_storage_menu.html',
        navigation_endpoints=(
            'object_storage_inventory.overview',
            'object_storage_inventory.systems',
            'object_storage_inventory.buckets',
        ),
        blueprint_vars=('object_storage_inventory_bp',),
        verifiers=('scripts/verify_object_storage_inventory_final_lock.py',),
        contract_paths=('tests/contracts/inventory/object_storage',),
        notes=(
            'Provider-neutral committed inventory. Live provider configuration, validation, and runtime health '
            'remain integration-owned.'
        ),
    ),
    ReleaseSurface(
        key='kubernetes_operations',
        title='Kubernetes Operations',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/kubernetes_operations_menu.html',
        navigation_endpoints=(
            'kubernetes_operations.configmap_management',
            'kubernetes_operations.secret_management',
        ),
        blueprint_vars=('kubernetes_operations_bp',),
        verifiers=('scripts/verify_kubernetes_operations_final_lock.py',),
        contract_paths=('tests/contracts/kubernetes_operations',),
    ),
    ReleaseSurface(
        key='governance',
        title='Kubernetes Governance',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/governance_menu.html',
        navigation_endpoints=('governance.tls_certificates',),
        blueprint_vars=('governance_bp',),
        verifiers=('scripts/verify_governance_final_lock.py',),
        contract_paths=('tests/contracts/governance',),
    ),
    ReleaseSurface(
        key='analytics',
        title='Analytics',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/analytics_menu.html',
        navigation_endpoints=(
            'analytics.overview',
            'analytics.utilization',
            'analytics.capacity',
            'analytics.storage',
            'analytics.workload',
            'analytics.forecast',
            'analytics.top_consumers',
            'analytics.alerts',
            'analytics.object_storage_overview',
            'analytics.object_storage_capacity',
            'analytics.object_storage_performance',
            'analytics.object_storage_forecast',
            'analytics.object_storage_top_consumers',
            'analytics.object_storage_alerts',
        ),
        blueprint_vars=('analytics_bp',),
        verifiers=(
            'scripts/verify_analytics_final_lock.py',
            'scripts/verify_object_storage_analytics.py',
        ),
        contract_paths=('tests/contracts/analytics',),
    ),
    ReleaseSurface(
        key='intelligence',
        title='Intelligence',
        lock_state='BASELINE LOCKED',
        navigation_source='app/templates/components/navigation/intelligence_menu.html',
        navigation_endpoints=(
            'intelligence.recommendations',
            'intelligence.alert_intelligence',
            'intelligence.catalog',
            'automation_control.index',
        ),
        blueprint_vars=('intelligence_bp', 'automation_control_bp'),
        verifiers=('scripts/verify_intelligence_baseline_lock.py',),
        contract_paths=('tests/contracts/intelligence',),
        notes='Automation mutations and reserved Server/HCI capability remain deferred and fail-closed.',
    ),
    ReleaseSurface(
        key='reports',
        title='Reports',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/reports_menu.html',
        navigation_endpoints=(
            'reports.overview',
            'reports.generate_report',
            'reports.generated_reports',
            'reports.report_templates',
            'reports.storage',
            'reports.schedules',
        ),
        blueprint_vars=('reports_bp',),
        verifiers=(
            'scripts/verify_report_generation_contract.py',
            'scripts/verify_report_job_standard.py',
            'scripts/verify_report_storage_resilience.py',
            'scripts/verify_report_runtime_imports.py',
        ),
        contract_paths=('tests/contracts/reports',),
    ),
    ReleaseSurface(
        key='integrations',
        title='Integrations',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/integrations_menu.html',
        navigation_endpoints=(
            'integrations.overview',
            'integrations.orchestration',
            'integrations.observability',
            'integrations.storage',
        ),
        blueprint_vars=('integrations_bp', 'cluster_bp', 'prometheus_bp', 'alertmanager_bp', 'minio_bp'),
        verifiers=(
            'scripts/verify_integration_provider_foundation.py',
            'scripts/verify_integration_domain_navigation.py',
            'scripts/verify_minio_object_storage_provider.py',
            'scripts/verify_integrations_final_lock.py',
        ),
        contract_paths=('tests/contracts/integrations',),
        notes='Provider workspaces are nested under Integration domains; cluster.* remains owned by Orchestration through Kubernetes navigation metadata and MinIO is owned by Storage → Object Storage.',
    ),
    ReleaseSurface(
        key='platform_operations',
        title='Platform Operations',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/platform_operations_menu.html',
        navigation_endpoints=(
            'platform_operations.overview.index',
            'jobs.executions',
            'platform_operations.data_lifecycle.index',
            'platform_operations.kubernetes.index',
        ),
        blueprint_vars=('platform_operations_bp', 'jobs_bp'),
        verifiers=(
            'scripts/verify_platform_operations_final_lock.py',
            'scripts/verify_job_progress_final_lock.py',
        ),
        contract_paths=('tests/contracts/platform_operations', 'tests/contracts/jobs'),
    ),
    ReleaseSurface(
        key='access',
        title='Access',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/access_management_menu.html',
        navigation_endpoints=(
            'access.overview.index',
            'users.index',
            'users.providers',
            'access.roles.index',
            'access.permissions.index',
            'notifications.activity_log',
        ),
        blueprint_vars=('access_bp', 'users_bp'),
        verifiers=('scripts/verify_access_final_lock.py',),
        contract_paths=('tests/contracts/access',),
    ),
    ReleaseSurface(
        key='settings',
        title='Settings',
        lock_state='LOCKED',
        navigation_source='app/templates/components/navigation/settings_menu.html',
        navigation_endpoints=('settings.general', 'settings.account'),
        blueprint_vars=('settings_bp',),
        verifiers=('scripts/verify_settings_final_lock.py',),
        contract_paths=('tests/contracts/settings',),
    ),
    ReleaseSurface(
        key='authentication',
        title='Authentication',
        lock_state='LOCKED',
        navigation_source=None,
        navigation_endpoints=(),
        blueprint_vars=('auth_bp',),
        verifiers=('scripts/verify_authentication_surface_final_lock.py',),
        contract_paths=('tests/contracts/auth',),
        notes='Public/shell surface; intentionally absent from authenticated sidebar navigation.',
    ),
    ReleaseSurface(
        key='notifications',
        title='Notification Center',
        lock_state='LOCKED',
        navigation_source=None,
        navigation_endpoints=(),
        blueprint_vars=('notifications_bp',),
        verifiers=(
            'scripts/verify_notification_center_final_lock.py',
            'scripts/verify_notification_activity_center.py',
        ),
        contract_paths=('tests/contracts/notifications',),
        notes='Application-shell surface; Activity Audit is separately linked under Access.',
    ),
    ReleaseSurface(
        key='health',
        title='Runtime Health',
        lock_state='SYSTEM LOCKED',
        navigation_source=None,
        navigation_endpoints=(),
        blueprint_vars=('health_bp',),
        verifiers=(),
        contract_paths=('tests/integration/release/test_release_endpoint_registry.py',),
        notes='Non-navigation liveness/readiness endpoints for deployment/runtime health.',
    ),
)


RUNTIME_ENDPOINTS: tuple[str, ...] = (
    'auth.login',
    'auth.logout',
    'notifications.center',
    'health.live',
    'health.ready',
    'cluster.add_cluster',
    'cluster.edit_cluster',
    'cluster.delete_cluster_route',
    'cluster.sync_all_clusters',
)


def navigation_endpoints() -> tuple[str, ...]:
    return tuple(endpoint for surface in SURFACES for endpoint in surface.navigation_endpoints)


def blueprint_vars() -> tuple[str, ...]:
    return tuple(variable for surface in SURFACES for variable in surface.blueprint_vars)
