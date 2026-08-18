from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.integrations.compatibility import (
    KUBERNETES_CURRENT_VERSION_LABEL,
    KUBERNETES_SUPPORTED_VERSION_LABEL,
    PROFILES,
)
from app.integrations.observability.metrics_source.providers import provider_definitions
from app.integrations.storage.object_storage.providers.minio.compatibility import (
    MINIO_COMPATIBILITY_PROFILES,
)
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

_STATIC_COMPATIBILITY_PRESENTATION: tuple[dict[str, Any], ...] = (
    {
        'key': 'kubernetes',
        'product': 'Kubernetes',
        'version_scheme': 'Semantic version',
        'icon': 'ship-wheel',
        'minimum_version': '1.20',
        'minimum_label': 'v1.20',
        'recommended_version': '1.36',
        'recommended_label': 'v1.36.x',
        'support_band': KUBERNETES_SUPPORTED_VERSION_LABEL,
        'current_band': KUBERNETES_CURRENT_VERSION_LABEL,
        'support_label': 'Current and Legacy Supported',
        'support_tone': 'info',
        'capability_summary': 'API discovery, inventory, governed operations, and TLS governance.',
        'validation_basis': 'Live API discovery and feature-level Kubernetes RBAC remain authoritative.',
    },
    {
        'key': 'alertmanager',
        'product': 'Alertmanager',
        'version_scheme': 'Semantic version',
        'icon': 'bell-ring',
        'minimum_version': '0.25',
        'minimum_label': 'v0.25',
        'recommended_version': '0.33',
        'recommended_label': 'v0.33.x',
        'support_band': 'v0.25–v0.33',
        'current_band': 'v0.27–v0.33',
        'support_label': 'API v2 Qualified',
        'support_tone': 'normal',
        'capability_summary': 'Alertmanager API v2 status, alerts, and silences contracts.',
        'validation_basis': 'Observed API metadata and binding scope must pass before alert analytics are considered ready.',
    },
)


def _metrics_compatibility_presentation() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for provider in provider_definitions():
        support = provider.support_presentation
        if support is None:
            continue
        rows.append(
            {
                'key': provider.key,
                'product': provider.label,
                'version_scheme': 'Semantic version',
                'icon': provider.icon,
                'minimum_version': support.minimum_version,
                'minimum_label': support.minimum_label,
                'recommended_version': support.recommended_version,
                'recommended_label': support.recommended_label,
                'support_band': support.support_band,
                'current_band': support.current_band,
                'support_label': support.support_label,
                'support_tone': support.support_tone,
                'capability_summary': support.capability_summary,
                'validation_basis': support.validation_basis,
            }
        )
    return tuple(rows)


def _object_storage_compatibility_presentation() -> dict[str, Any] | None:
    if not MINIO_COMPATIBILITY_PROFILES:
        return None
    profile = MINIO_COMPATIBILITY_PROFILES[0]
    return {
        'key': 'minio',
        'product': 'MinIO',
        'version_scheme': 'Release identifier',
        'minimum_version': profile.minimum_release,
        'minimum_label': profile.minimum_release,
        'recommended_version': profile.maximum_release,
        'recommended_label': profile.maximum_release,
        'support_band': profile.supported_range_label,
        'current_band': profile.label,
        'support_label': 'Qualified Release',
        'support_tone': 'normal',
        'capability_summary': 'S3 API reachability, product identity, bucket discovery, and optional object-storage governance capabilities.',
        'validation_basis': 'The declared MinIO release must match a qualified provider profile; live S3/API validation and observability consumer bindings remain independently authoritative.',
        'profiles': tuple(
            {
                'key': item.key,
                'version_constraint': item.supported_range_label,
                'support_level': item.support_level,
            }
            for item in MINIO_COMPATIBILITY_PROFILES
        ),
    }


def _clean_config_value(value: Any, fallback: str = 'Not provided') -> str:
    normalized = str(value or '').strip()
    return normalized or fallback


def _compatibility_catalog() -> tuple[dict[str, Any], ...]:
    catalog: list[dict[str, Any]] = []
    minio = _object_storage_compatibility_presentation()
    presentations = (
        _STATIC_COMPATIBILITY_PRESENTATION[0],
        *_metrics_compatibility_presentation(),
        *_STATIC_COMPATIBILITY_PRESENTATION[1:],
        *((minio,) if minio else ()),
    )
    for presentation in presentations:
        explicit_profiles = presentation.get('profiles')
        if explicit_profiles is not None:
            profiles = tuple(explicit_profiles)
        else:
            profiles = tuple(
                {
                    'key': profile.key,
                    'version_constraint': profile.version_constraint,
                    'support_level': profile.support_level,
                }
                for profile in PROFILES.get(presentation['key'], ())
            )
        catalog.append(
            {
                **presentation,
                'profiles': profiles,
                'profile_count': len(profiles),
            }
        )
    return tuple(catalog)


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
        'compatibility_products': compatibility_products,
        'compatibility_product_count': len(compatibility_products),
        'compatibility_profile_count': sum(item['profile_count'] for item in compatibility_products),
    }
