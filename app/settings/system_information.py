from __future__ import annotations
from app.cluster.constants import get_environment_label

from collections.abc import Mapping
from typing import Any

_RELEASE_FEATURES: tuple[dict[str, Any], ...] = (
    {
        'title': 'Identity & Access',
        'icon': 'shield-check',
        'description': 'Provider-neutral authentication and KAORI authorization controls.',
        'features': (
            'Local Database break-glass authentication',
            'LDAP / Active Directory provisioning and sign-in',
            'Google OpenID Connect and GitHub OAuth',
            'Role-based access, account lifecycle, and Super Admin guardrails',
            'Unified authentication and administrative activity audit',
        ),
    },
    {
        'title': 'Kubernetes Operations',
        'icon': 'boxes',
        'description': 'Centralized operational visibility and controlled Kubernetes workflows.',
        'features': (
            'Cluster registration, validation, synchronization, and inventory',
            'Nodes, namespaces, workloads, Pods, Services, Ingresses, storage, and topology',
            'Secret and ConfigMap operational workflows',
            'TLS Secret governance and protected reveal controls',
        ),
    },
    {
        'title': 'Analytics & Intelligence',
        'icon': 'brain-circuit',
        'description': 'Operational analytics that use connected infrastructure signals.',
        'features': (
            'Utilization, capacity, storage, workload, and forecast analytics',
            'Top consumers, alerts, anomalies, and recommendation workflows',
            'Versioned Prometheus and Alertmanager compatibility profiles',
        ),
    },
    {
        'title': 'Reporting & Retention',
        'icon': 'file-chart-column',
        'description': 'Report generation, storage, scheduling foundations, and audit retention.',
        'features': (
            'PDF report generation and generated report management',
            'System and custom report templates',
            'Local and S3-compatible storage backends',
            'Archive-first operational activity retention',
        ),
    },
    {
        'title': 'Personal Workspace',
        'icon': 'user-round-cog',
        'description': 'Per-user presentation and account security preferences.',
        'features': (
            'Automatic or manual IANA timezone selection',
            'Regional date, time, and locale presentation',
            'Account identity, credential ownership, and authentication history',
            'Personal Notification Center',
        ),
    },
    {
        'title': 'Integrations',
        'icon': 'unplug',
        'description': 'Provider-neutral integration administration and readiness validation.',
        'features': (
            'Prometheus inventory and configuration',
            'Alertmanager inventory and configuration',
            'Direct and indirect integration modes',
            'Externalized runtime secrets for identity and infrastructure providers',
        ),
    },
)


def _clean_config_value(value: Any, fallback: str = 'Not provided') -> str:
    normalized = str(value or '').strip()
    return normalized or fallback


def build_system_information(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe, user-visible KAORI release information.

    This context intentionally excludes infrastructure endpoints, credentials,
    secret names, database details, and other deployment-sensitive values.
    """
    version = _clean_config_value(config.get('APP_VERSION'), 'Unversioned')
    environment = get_environment_label(_clean_config_value(config.get('APP_ENV'), 'development'))
    build_sha = _clean_config_value(config.get('APP_BUILD_SHA'), 'Not provided')
    build_date = _clean_config_value(config.get('APP_BUILD_DATE'), 'Not provided')

    return {
        'product_name': _clean_config_value(config.get('APP_NAME'), 'KAORI'),
        'version': version,
        'environment': environment,
        'build_sha': build_sha,
        'build_date': build_date,
        'feature_groups': _RELEASE_FEATURES,
        'feature_group_count': len(_RELEASE_FEATURES),
        'feature_count': sum(len(group['features']) for group in _RELEASE_FEATURES),
    }
