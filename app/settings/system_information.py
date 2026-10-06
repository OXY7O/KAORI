from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.integrations.compatibility import COMPATIBILITY_LIFECYCLE_POLICY, PRODUCT_POLICIES, QUALIFICATIONS
from app.integrations.storage.object_storage.providers.minio.capabilities import CAPABILITY_PROFILE
from app.integrations.storage.object_storage.providers.minio.compatibility import MINIO_COMPATIBILITY_PROFILES
from app.kubernetes.cluster.constants import get_environment_label

_RELEASE_HIGHLIGHTS: tuple[dict[str, str], ...] = (
    {
        'title': 'Provider-Neutral Integration Lifecycle',
        'icon': 'unplug',
        'description': (
            'Kubernetes, Prometheus, Thanos Query, Alertmanager, and MinIO now follow clearer provider, compatibility, capability, validation, binding, and consumer-readiness ownership boundaries.'
        ),
    },
    {
        'title': 'Operations & Data Lifecycle Control Plane',
        'icon': 'workflow',
        'description': (
            'Jobs, execution evidence, Data Lifecycle, notifications, object-storage analytics, and controlled automation surfaces converge on shared operational feedback and worker-owned execution contracts.'
        ),
    },
    {
        'title': 'Release Reliability & Identity Hardening',
        'icon': 'shield-check',
        'description': (
            'Release metadata, final gates, Access and Identity Provider boundaries, runtime imports, type safety, and regression contracts are tightened for a reproducible 2.3.0 deployment baseline.'
        ),
    },
)

_RELEASE_FEATURES: tuple[dict[str, Any], ...] = (
    {
        'title': 'Identity & Access',
        'icon': 'shield-check',
        'description': 'Provider-neutral authentication and authoritative KAORI authorization controls.',
        'features': (
            'Local Database break-glass authentication',
            'LDAP / Active Directory provisioning and sign-in',
            'Google OpenID Connect and GitHub OAuth',
            'Role-based access, account lifecycle, and Super Admin guardrails',
            'Unified authentication and administrative Activity Audit evidence',
        ),
    },
    {
        'title': 'Kubernetes Platform Operations',
        'icon': 'boxes',
        'description': 'Inventory, governed mutations, advanced administration, and recovery-aware synchronization.',
        'features': (
            'Cluster registration, validation, runtime readiness, and automatic or manual inventory synchronization',
            'Nodes, namespaces, workloads, Pods, Services, Ingresses, storage, configuration, and topology inventory',
            'Validated ConfigMap and Secret create, update, replacement, and delete workflows',
            'Protected one-time Secret Reveal under Platform Operations → Kubernetes Administration',
            'TLS certificate inventory, governance, bulk rotation, and worker-based automatic synchronization',
        ),
    },
    {
        'title': 'Analytics & Intelligence',
        'icon': 'brain-circuit',
        'description': 'Worker-materialized operational analytics built from committed infrastructure snapshots.',
        'features': (
            'Kubernetes Operations Dashboard with inventory, capacity, forecast, consumer, alert, and reporting summaries',
            'Resource utilization, capacity, storage, workload, forecast, top-consumer, and alert analytics',
            'Internal content tabs that keep analytics pages compact without removing canonical navigation',
            'Forecast and growth-risk visualization with historical and projected utilization',
            'Recommendation, alert intelligence, anomaly, and operational response guidance',
        ),
    },
    {
        'title': 'Integration Runtime & Compatibility',
        'icon': 'unplug',
        'description': 'Versioned adapters, live capability evidence, and recovery monitoring for infrastructure providers.',
        'features': (
            'Kubernetes, Prometheus, Thanos Query, Alertmanager, and MinIO compatibility profiles',
            'Provider-neutral Metrics Source registration with Prometheus and Thanos Query adapters plus asset-scoped consumer bindings',
            'Runtime observations, readiness validation, and capability evidence collection',
            'Automatic runtime monitoring with targeted recovery refresh after connectivity returns',
            'User-friendly source failure presentation without exposing raw endpoints or exceptions',
        ),
    },
    {
        'title': 'Jobs & Automation',
        'icon': 'timer-reset',
        'description': 'Registered background execution policies with dedicated queues, progress, and auditable outcomes.',
        'features': (
            'Celery Beat scheduling with canonical job definitions and configurable policies',
            'Manual, scheduled, and recovery-triggered execution paths',
            'Inventory, analytics, integration runtime, Data Lifecycle, and TLS synchronization workloads',
            'Job deduplication, progress reporting, partial-success handling, and execution history',
        ),
    },
    {
        'title': 'Reporting & Artifact Delivery',
        'icon': 'file-chart-column',
        'description': 'Template-driven report delivery, generated artifacts, scheduling, and governed storage.',
        'features': (
            'Existing system and custom report templates with configurable sections and ordering',
            'Canonical WeasyPrint HTML/PDF rendering',
            'Generated report management, schedules, local storage, and S3-compatible storage',
        ),
    },
    {
        'title': 'Personal Workspace',
        'icon': 'user-round-cog',
        'description': 'Per-user presentation, identity context, credential ownership, and notification preferences.',
        'features': (
            'Automatic or manual IANA timezone selection',
            'Regional date, time, and locale presentation',
            'Account identity, credential ownership, and authentication history',
            'Persistent personal Notification Center and Activity Audit access',
        ),
    },
)


def _object_storage_compatibility_presentation() -> dict[str, Any] | None:
    if not MINIO_COMPATIBILITY_PROFILES:
        return None
    profiles = MINIO_COMPATIBILITY_PROFILES
    first = profiles[0]
    return {
        'key': 'minio',
        'product': 'MinIO',
        'version_scheme': 'Release identifier',
        'icon': 'database',
        'contract_profile': CAPABILITY_PROFILE,
        'minimum_label': first.minimum_release,
        'recommended_label': profiles[-1].maximum_release,
        'qualified_versions': '; '.join(item.supported_range_label for item in profiles),
        'upstream_lifecycle': 'Community repository archived; qualified release evidence remains explicit.',
        'support_label': 'Extended · Upstream Archived',
        'support_tone': 'warning',
        'policy_version': f'v{COMPATIBILITY_LIFECYCLE_POLICY.version}',
        'policy_year': COMPATIBILITY_LIFECYCLE_POLICY.policy_year,
        'policy_window': COMPATIBILITY_LIFECYCLE_POLICY.window_label,
        'capability_summary': (
            'S3 API reachability, bucket discovery, and optional object-storage governance capabilities.'
        ),
        'validation_basis': (
            'Live S3 capability evidence decides readiness. MinIO release qualification is supporting evidence; '
            'an unqualified release is degraded rather than blocked by version alone.'
        ),
        'profiles': tuple(
            {
                'key': item.key,
                'version_constraint': item.supported_range_label,
                'support_level': item.support_level,
                'upstream_lifecycle': item.upstream_lifecycle,
                'contract_profile': item.contract_profile,
            }
            for item in profiles
        ),
        'profile_count': len(profiles),
    }


def _compatibility_catalog() -> tuple[dict[str, Any], ...]:
    catalog: list[dict[str, Any]] = []
    for key in ('kubernetes', 'prometheus', 'thanos', 'alertmanager'):
        policy = PRODUCT_POLICIES[key]
        qualifications = QUALIFICATIONS.get(key, ())
        catalog.append(
            {
                'key': policy.key,
                'product': policy.label,
                'version_scheme': policy.version_scheme,
                'icon': policy.icon,
                'contract_profile': policy.contract_profile,
                'minimum_label': policy.minimum_label,
                'recommended_label': policy.recommended_label,
                'qualified_versions': policy.qualified_version_label,
                'upstream_lifecycle': policy.upstream_lifecycle_label,
                'support_label': policy.support_label,
                'support_tone': policy.support_tone,
                'policy_version': f'v{COMPATIBILITY_LIFECYCLE_POLICY.version}',
                'policy_year': COMPATIBILITY_LIFECYCLE_POLICY.policy_year,
                'policy_window': COMPATIBILITY_LIFECYCLE_POLICY.window_label,
                'capability_summary': policy.capability_summary,
                'validation_basis': policy.validation_basis,
                'profiles': tuple(
                    {
                        'key': item.key,
                        'version_constraint': item.version_constraint,
                        'support_level': item.support_level,
                        'upstream_lifecycle': item.upstream_lifecycle,
                        'contract_profile': item.contract_profile,
                    }
                    for item in qualifications
                ),
                'profile_count': len(qualifications),
            }
        )
    minio = _object_storage_compatibility_presentation()
    if minio:
        catalog.append(minio)
    return tuple(catalog)


def _clean_config_value(value: Any, fallback: str = 'Not provided') -> str:
    normalized = str(value or '').strip()
    return normalized or fallback


def build_system_information(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe, user-visible KAORI release and compatibility information.

    This context intentionally excludes infrastructure endpoints, credentials,
    secret names, database details, and other deployment-sensitive values.
    """
    version = _clean_config_value(config.get('APP_VERSION'), 'Unversioned')
    environment = get_environment_label(_clean_config_value(config.get('APP_ENV'), 'development'))
    build_sha = _clean_config_value(config.get('APP_BUILD_SHA'), 'Not provided')
    build_date = _clean_config_value(config.get('APP_BUILD_DATE'), 'Not provided')
    compatibility_products = _compatibility_catalog()

    return {
        'product_name': _clean_config_value(config.get('APP_NAME'), 'KAORI'),
        'version': version,
        'release_label': f'KAORI {version}',
        'environment': environment,
        'build_sha': build_sha,
        'build_date': build_date,
        'release_highlights': _RELEASE_HIGHLIGHTS,
        'release_highlight_count': len(_RELEASE_HIGHLIGHTS),
        'feature_groups': _RELEASE_FEATURES,
        'feature_group_count': len(_RELEASE_FEATURES),
        'feature_count': sum(len(group['features']) for group in _RELEASE_FEATURES),
        'compatibility_policy_key': COMPATIBILITY_LIFECYCLE_POLICY.key,
        'compatibility_policy_version': COMPATIBILITY_LIFECYCLE_POLICY.version,
        'compatibility_policy_year': COMPATIBILITY_LIFECYCLE_POLICY.policy_year,
        'compatibility_policy_snapshot_date': COMPATIBILITY_LIFECYCLE_POLICY.snapshot_date,
        'compatibility_lookback_years': COMPATIBILITY_LIFECYCLE_POLICY.lookback_years,
        'compatibility_anchor_year': COMPATIBILITY_LIFECYCLE_POLICY.anchor_year,
        'compatibility_window_label': COMPATIBILITY_LIFECYCLE_POLICY.window_label,
        'compatibility_products': compatibility_products,
        'compatibility_product_count': len(compatibility_products),
        'compatibility_profile_count': sum(item['profile_count'] for item in compatibility_products),
        'compatibility_contract_count': len({item['contract_profile'] for item in compatibility_products}),
        'compatibility_qualification_count': sum(item['profile_count'] for item in compatibility_products),
    }
