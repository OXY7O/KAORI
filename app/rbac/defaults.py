from __future__ import annotations

DEFAULT_PERMISSIONS = [
    ('welcome.view', 'workspace', 'view', 'View the OpsIn Observability welcome workspace.'),
    ('dashboard.view', 'k8s_dashboard', 'view', 'View the Kubernetes operations dashboard.'),
    ('clusters.view', 'k8s_cluster', 'view', 'View Kubernetes cluster records and connection status.'),
    ('clusters.manage', 'k8s_cluster', 'manage', 'Create, edit, and delete Kubernetes cluster records.'),
    ('clusters.sync', 'k8s_cluster', 'sync', 'Run Kubernetes cluster connectivity and inventory sync actions.'),
    ('inventory.view', 'k8s_inventory', 'view', 'View Kubernetes inventory pages.'),
    ('kubernetes_secrets.view', 'k8s_operations', 'view_secret_management', 'View Kubernetes Secret Management operations.'),
    ('kubernetes_secrets.create', 'k8s_operations', 'create_secret', 'Create validated Kubernetes Secrets through guided workflows.'),
    ('kubernetes_secrets.rotate_tls', 'k8s_operations', 'rotate_tls_secret', 'Validate and rotate an existing Kubernetes TLS Secret.'),
    ('kubernetes_secrets.bulk_rotate_tls', 'k8s_operations', 'bulk_rotate_tls_secret', 'Validate and rotate multiple Kubernetes TLS Secrets.'),
    ('analytics.view', 'k8s_analytics', 'view', 'View Kubernetes analytics, capacity, trend, and alert pages.'),
    ('governance.view', 'governance', 'view', 'View Kubernetes governance workspace and navigation.'),
    (
        'tls_certificates.view',
        'governance',
        'view_tls_certificates',
        'View Kubernetes TLS certificate inventory, expiry, issuer, and usage mapping.',
    ),
    (
        'tls_certificates.sync',
        'governance',
        'sync_tls_certificates',
        'Refresh TLS certificate metadata from Kubernetes TLS Secrets.',
    ),
    (
        'tls_certificates.update',
        'governance',
        'update_tls_certificates',
        'Update an existing Kubernetes TLS Secret using a validated certificate and private key upload.',
    ),
    (
        'tls_certificates.bulk_update',
        'governance',
        'bulk_update_tls_certificates',
        'Update multiple selected Kubernetes TLS Secrets using a validated certificate and private key upload.',
    ),
    (
        'intelligence.view',
        'intelligence',
        'view',
        'View recommendation, alert intelligence, and intelligence catalog navigation.',
    ),
    ('reports.view', 'reports', 'view', 'View generated reports and reporting overview.'),
    ('reports.generate', 'reports', 'generate', 'Generate and export operational reports.'),
    ('reports.manage_templates', 'reports', 'manage_templates', 'Manage report templates.'),
    ('reports.manage_schedules', 'reports', 'manage_schedules', 'Manage report schedules.'),
    ('reports.manage_storage', 'reports', 'manage_storage', 'Manage report storage verification and cleanup.'),
    ('settings.view', 'settings', 'view', 'View settings pages.'),
    (
        'settings.manage_integrations',
        'settings',
        'manage_integrations',
        'Manage Prometheus, Alertmanager, and reporting integrations.',
    ),
    ('settings.view_login_activity', 'access', 'view_login_activity', 'View login activity and authentication events.'),
    (
        'settings.view_operational_activity',
        'access',
        'view_operational_activity',
        'View cross-user operational activity and background action audit records.',
    ),
    (
        'settings.export_operational_activity',
        'access',
        'export_operational_activity',
        'Download operational activity archive data and manifests.',
    ),
    (
        'settings.manage_operational_activity_retention',
        'access',
        'manage_operational_activity_retention',
        'Preview, run, verify, and maintain operational activity retention archives.',
    ),
    ('users.view', 'access', 'view_users', 'View user accounts and access assignments.'),
    ('users.manage', 'access', 'manage_users', 'Create and update user accounts.'),
    ('users.reset_password', 'access', 'reset_user_password', 'Reset passwords for database-managed user accounts.'),
    ('users.activate', 'access', 'activate_users', 'Activate or deactivate local application access.'),
    ('users.delete', 'access', 'delete_users', 'Soft delete user accounts.'),
    ('roles.view', 'access', 'view_roles', 'View roles and permission assignments.'),
    ('roles.manage', 'access', 'manage_roles', 'Create and update custom roles.'),
    ('system.view', 'system', 'view', 'View system information.'),
    ('system.manage', 'system', 'manage', 'Manage system-level settings.'),
]

DEFAULT_ROLE_DEFINITIONS = {
    'viewer': {
        'display_name': 'Viewer',
        'description': 'Read-only access to the welcome workspace, Kubernetes dashboard, inventory, analytics, and reports.',
    },
    'operator': {
        'display_name': 'Operator',
        'description': 'Operational access for sync actions, report generation, and daily review.',
    },
    'editor': {
        'display_name': 'Editor',
        'description': 'Configuration access for clusters, integrations, templates, and schedules.',
    },
    'admin': {
        'display_name': 'Admin',
        'description': 'Administrative access to users, roles, integrations, and protected settings.',
    },
    'auditor': {
        'display_name': 'Auditor',
        'description': 'Read-only audit and security visibility without operational write access.',
    },
}

DEFAULT_ROLE_PERMISSIONS = {
    'viewer': {
        'welcome.view', 'dashboard.view', 'clusters.view', 'inventory.view',
        'analytics.view', 'governance.view', 'tls_certificates.view',
        'intelligence.view', 'reports.view', 'settings.view',
    },
    'operator': {
        'welcome.view', 'dashboard.view', 'clusters.view', 'clusters.sync',
        'inventory.view', 'analytics.view', 'governance.view',
        'tls_certificates.view', 'tls_certificates.sync',
        'kubernetes_secrets.view', 'kubernetes_secrets.rotate_tls',
        'intelligence.view', 'reports.view', 'reports.generate', 'settings.view',
    },
    'editor': {
        'welcome.view', 'dashboard.view', 'clusters.view', 'clusters.manage',
        'clusters.sync', 'inventory.view', 'analytics.view', 'governance.view',
        'tls_certificates.view', 'tls_certificates.sync',
        'kubernetes_secrets.view', 'kubernetes_secrets.create',
        'kubernetes_secrets.rotate_tls', 'kubernetes_secrets.bulk_rotate_tls',
        'intelligence.view', 'reports.view', 'reports.generate',
        'reports.manage_templates', 'reports.manage_schedules',
        'reports.manage_storage', 'settings.view', 'settings.manage_integrations',
    },
    'admin': {permission[0] for permission in DEFAULT_PERMISSIONS},
    'auditor': {
        'welcome.view', 'dashboard.view', 'clusters.view', 'inventory.view',
        'analytics.view', 'governance.view', 'tls_certificates.view',
        'intelligence.view', 'reports.view', 'settings.view',
        'settings.view_login_activity', 'settings.view_operational_activity',
        'settings.export_operational_activity', 'users.view', 'roles.view',
        'system.view',
    },
}
