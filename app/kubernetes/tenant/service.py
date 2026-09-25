from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.capacity_governance import (
    build_capacity_governance_summary,
    enforce_namespace_allocation_preflight,
)
from app.kubernetes.tenant.provisioning import create_namespace_intent, reconcile_native_namespace
from app.kubernetes.tenant.validation import validate_profile_spec
from app.models import Cluster
from app.models.cluster import ClusterStatus
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
    TenantCapacityDecision,
    TenantEnvironment,
    TenantEnvironmentName,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantResourceProfile,
    TenantResourceProfileClass,
)

_TENANT_SLUG_RE = re.compile(r'[^a-z0-9-]+')
_ALLOWED_ENVIRONMENTS = {item.value for item in TenantEnvironmentName}
_ALLOWED_PROFILE_CLASSES = {item.value for item in TenantResourceProfileClass}

RESOURCE_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    'small': {
        'version': 1,
        'quota': {
            'requests.cpu': '1',
            'limits.cpu': '2',
            'requests.memory': '2Gi',
            'limits.memory': '4Gi',
            'pods': '10',
            'persistentvolumeclaims': '5',
            'requests.storage': '50Gi',
            'services': '5',
            'configmaps': '25',
            'secrets': '25',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '250m', 'memory': '256Mi'},
        },
    },
    'standard': {
        'version': 1,
        'quota': {
            'requests.cpu': '2',
            'limits.cpu': '4',
            'requests.memory': '4Gi',
            'limits.memory': '8Gi',
            'pods': '20',
            'persistentvolumeclaims': '10',
            'requests.storage': '100Gi',
            'services': '10',
            'configmaps': '50',
            'secrets': '50',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '500m', 'memory': '512Mi'},
        },
    },
    'large': {
        'version': 1,
        'quota': {
            'requests.cpu': '4',
            'limits.cpu': '8',
            'requests.memory': '8Gi',
            'limits.memory': '16Gi',
            'pods': '40',
            'persistentvolumeclaims': '20',
            'requests.storage': '200Gi',
            'services': '20',
            'configmaps': '100',
            'secrets': '100',
        },
        'limits': {
            'default_request': {'cpu': '250m', 'memory': '256Mi'},
            'default': {'cpu': '1', 'memory': '1Gi'},
        },
    },
}


class TenantStateConflictError(RuntimeError):
    """Committed Tenant state changed while a mutation transaction was applying."""


def _text(source: Mapping[str, Any], key: str) -> str:
    return str(source.get(key) or '').strip()


def normalize_tenant_slug(value: str) -> str:
    slug = _TENANT_SLUG_RE.sub('-', value.strip().lower().replace('_', '-').replace(' ', '-'))
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug or len(slug) > 63:
        raise ValueError('Tenant slug must contain 1–63 lowercase letters, numbers, or hyphens.')
    return slug


def get_ready_native_clusters() -> list[Cluster]:
    return (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(
            Cluster.status == ClusterStatus.CONNECTED.value,
            KubernetesConnection.readiness_status == 'ready',
        )
        .order_by(Cluster.name.asc())
        .all()
    )


def create_tenant(source: Mapping[str, Any]) -> tuple[Tenant, TenantEnvironment]:
    name = _text(source, 'name')
    if not name or len(name) > 120:
        raise ValueError('Tenant name is required and must be at most 120 characters.')

    slug = normalize_tenant_slug(_text(source, 'slug') or name)
    environment = _text(source, 'environment').lower()
    if environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError('Select a supported Tenant environment.')

    cluster_id = _text(source, 'cluster_id')
    cluster = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(
            Cluster.id == cluster_id,
            Cluster.status == ClusterStatus.CONNECTED.value,
            KubernetesConnection.readiness_status == 'ready',
        )
        .first()
    )
    if cluster is None:
        raise ValueError('Select a connected Kubernetes cluster with Ready integration capability.')

    if Tenant.query.filter_by(cluster_id=cluster.id, slug=slug).first() is not None:
        raise ValueError('A Tenant with this slug already exists on the selected cluster.')

    tenant = Tenant()
    tenant.cluster_id = cluster.id
    tenant.name = name
    tenant.slug = slug
    tenant.description = _text(source, 'description') or None
    tenant.lifecycle_status = TenantLifecycleStatus.READY.value
    tenant.provider_key = 'native_kubernetes'
    tenant.provider_state = 'native'
    tenant.reconciliation_authority = 'native_kubernetes'
    tenant.provider_evidence_json = {
        'provider': 'native_kubernetes',
        'readiness': 'ready',
        'connection_id': cluster.kubernetes_connection.id if cluster.kubernetes_connection else None,
        'source': 'kubernetes_connection',
    }
    db.session.add(tenant)
    db.session.flush()

    tenant_environment = TenantEnvironment()
    tenant_environment.tenant_id = tenant.id
    tenant_environment.environment = environment
    db.session.add(tenant_environment)
    db.session.flush()
    return tenant, tenant_environment


def create_tenant_committed(source: Mapping[str, Any]) -> tuple[Tenant, TenantEnvironment]:
    try:
        tenant, environment = create_tenant(source)
        db.session.commit()
        return tenant, environment
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed Tenant state changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _profile_values(source: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    quota_fields = {
        'requests_cpu': 'requests.cpu',
        'limits_cpu': 'limits.cpu',
        'requests_memory': 'requests.memory',
        'limits_memory': 'limits.memory',
        'pods': 'pods',
        'persistentvolumeclaims': 'persistentvolumeclaims',
        'requests_storage': 'requests.storage',
        'services': 'services',
        'configmaps': 'configmaps',
        'secrets': 'secrets',
    }
    quota = {target: value for field, target in quota_fields.items() if (value := _text(source, field))}

    limit_fields = {
        'default_cpu': ('default', 'cpu'),
        'default_memory': ('default', 'memory'),
        'default_request_cpu': ('default_request', 'cpu'),
        'default_request_memory': ('default_request', 'memory'),
    }
    limits: dict[str, dict[str, str]] = {}
    for field, (group, resource) in limit_fields.items():
        value = _text(source, field)
        if value:
            limits.setdefault(group, {})[resource] = value

    return validate_profile_spec(quota, limits)


def _resource_profile_values(
    profile_class: str,
    source: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, str]], int, str | None, int | None]:
    if profile_class in RESOURCE_PROFILE_PRESETS:
        preset = RESOURCE_PROFILE_PRESETS[profile_class]
        quota, limits = validate_profile_spec(preset['quota'], preset['limits'])
        return quota, limits, int(preset['version']), None, None

    base_preset_class = _text(source, 'base_preset_class').lower() or None
    if base_preset_class is not None and base_preset_class not in RESOURCE_PROFILE_PRESETS:
        raise ValueError('Select a supported base preset for the Custom Resource Profile.')

    quota, limits = _profile_values(source)
    base_preset_version = (
        int(RESOURCE_PROFILE_PRESETS[base_preset_class]['version']) if base_preset_class is not None else None
    )
    return quota, limits, 1, base_preset_class, base_preset_version


def _namespace_allocation_values(
    profile: TenantResourceProfile,
) -> tuple[dict[str, str], dict[str, dict[str, str]], bool]:
    if profile.profile_class in RESOURCE_PROFILE_PRESETS:
        preset = RESOURCE_PROFILE_PRESETS[profile.profile_class]
        quota, limits = validate_profile_spec(preset['quota'], preset['limits'])
        return quota, limits, False

    quota, limits = validate_profile_spec(
        profile.quota_hard_json or {},
        profile.limit_defaults_json or {},
    )
    return quota, limits, True


def create_resource_profile(source: Mapping[str, Any]) -> TenantResourceProfile:
    name = _text(source, 'profile_name')
    if not name or len(name) > 120:
        raise ValueError('Resource Profile name is required and must be at most 120 characters.')
    if TenantResourceProfile.query.filter(func.lower(TenantResourceProfile.name) == name.lower()).first() is not None:
        raise ValueError('A Resource Profile with this name already exists.')

    profile_class = _text(source, 'profile_class').lower()
    if profile_class not in _ALLOWED_PROFILE_CLASSES:
        raise ValueError('Select a supported Resource Profile class.')

    quota, limits, version, base_preset_class, base_preset_version = _resource_profile_values(profile_class, source)
    profile = TenantResourceProfile()
    profile.name = name
    profile.profile_class = profile_class
    profile.version = version
    profile.base_preset_class = base_preset_class
    profile.base_preset_version = base_preset_version
    profile.description = _text(source, 'profile_description') or None
    profile.quota_hard_json = quota
    profile.limit_defaults_json = limits
    profile.enabled = True
    db.session.add(profile)
    db.session.flush()
    return profile


def create_resource_profile_committed(source: Mapping[str, Any]) -> TenantResourceProfile:
    try:
        profile = create_resource_profile(source)
        db.session.commit()
        return profile
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed Resource Profile state changed while this request was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def provision_native_namespace(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        environment_id = int(_text(source, 'tenant_environment_id'))
        profile_id = int(_text(source, 'resource_profile_id'))
    except ValueError as exc:
        raise ValueError('Select a Tenant environment and Resource Profile.') from exc

    environment = db.session.get(TenantEnvironment, environment_id)
    profile = db.session.get(TenantResourceProfile, profile_id)
    if environment is None:
        raise ValueError('Selected Tenant environment no longer exists.')
    if profile is None or not profile.enabled:
        raise ValueError('Selected Resource Profile is unavailable.')

    tenant = environment.tenant
    if tenant.provider_key != 'native_kubernetes':
        raise ValueError('This UAT slice can provision only Native Kubernetes Tenant bindings.')

    namespace = _text(source, 'namespace')
    if TenantNamespace.query.filter_by(cluster_id=tenant.cluster_id, namespace=namespace).first() is not None:
        raise ValueError('This namespace is already tracked by Tenant Management on the selected cluster.')

    quota, limits, customized = _namespace_allocation_values(profile)
    capacity_decision = enforce_namespace_allocation_preflight(
        tenant_environment=environment,
        profile=profile,
        namespace=namespace,
        quota_hard=quota,
    )
    record = create_namespace_intent(
        tenant_environment=environment,
        profile=profile,
        namespace=namespace,
        quota_hard=quota,
        limit_defaults=limits,
        allocation_customized=customized,
    )
    record.capacity_decision_id = capacity_decision.id
    try:
        reconcile_native_namespace(record)
    except (ApiException, ValueError):
        db.session.commit()
        raise
    db.session.commit()
    return record


def provision_native_namespace_committed(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        return provision_native_namespace(source)
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed Tenant namespace state changed while this request was being applied. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def get_tenant_context() -> dict[str, Any]:
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).limit(5).all()
    profiles = TenantResourceProfile.query.order_by(TenantResourceProfile.created_at.desc()).limit(5).all()
    namespaces = TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).limit(5).all()
    environment_options = (
        TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value)
        .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
        .all()
    )
    ready_clusters = get_ready_native_clusters()
    capacity_governance = [
        {'cluster': cluster, **build_capacity_governance_summary(cluster.id)} for cluster in ready_clusters
    ]
    capacity_decisions = TenantCapacityDecision.query.order_by(TenantCapacityDecision.created_at.desc()).limit(5).all()
    namespace_count = TenantNamespace.query.count()
    return {
        'tenants': tenants,
        'profiles': profiles,
        'namespaces': namespaces,
        'environment_options': environment_options,
        'ready_clusters': ready_clusters,
        'capacity_governance': capacity_governance,
        'capacity_decisions': capacity_decisions,
        'tenant_count': Tenant.query.count(),
        'profile_count': TenantResourceProfile.query.count(),
        'namespace_count': namespace_count,
        'ready_namespace_count': TenantNamespace.query.filter_by(provisioning_status='ready').count(),
        'native_available': bool(ready_clusters),
        'resource_profile_presets': RESOURCE_PROFILE_PRESETS,
        'namespace_allocation_profiles': {
            str(profile.id): {
                'quota': (
                    RESOURCE_PROFILE_PRESETS[profile.profile_class]['quota']
                    if profile.profile_class in RESOURCE_PROFILE_PRESETS
                    else profile.quota_hard_json or {}
                ),
                'limits': (
                    RESOURCE_PROFILE_PRESETS[profile.profile_class]['limits']
                    if profile.profile_class in RESOURCE_PROFILE_PRESETS
                    else profile.limit_defaults_json or {}
                ),
                'version': (
                    int(RESOURCE_PROFILE_PRESETS[profile.profile_class]['version'])
                    if profile.profile_class in RESOURCE_PROFILE_PRESETS
                    else profile.version
                ),
                'profile_class': profile.profile_class,
            }
            for profile in profiles
            if profile.enabled
        },
    }
