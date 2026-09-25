from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.provisioning import create_namespace_intent, reconcile_native_namespace
from app.kubernetes.tenant.validation import validate_profile_spec
from app.models import Cluster
from app.models.cluster import ClusterStatus
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
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
_OPERATION_TABS = {'provisioning', 'runs-evidence', 'drift-reconcile', 'activity'}

RESOURCE_PROFILE_PRESETS: dict[str, dict[str, dict[str, str]]] = {
    'small': {
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


def _custom_profile_values(source: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
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

    if not limits:
        raise ValueError('Custom Resource Profile must define at least one Container LimitRange default or request.')
    return validate_profile_spec(quota, limits)


def profile_values(
    profile_class: str,
    source: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    if profile_class in RESOURCE_PROFILE_PRESETS:
        preset = RESOURCE_PROFILE_PRESETS[profile_class]
        return validate_profile_spec(copy.deepcopy(preset['quota']), copy.deepcopy(preset['limits']))
    if profile_class == TenantResourceProfileClass.CUSTOM.value:
        return _custom_profile_values(source)
    raise ValueError('Select a supported Resource Profile class.')


def create_resource_profile(source: Mapping[str, Any]) -> TenantResourceProfile:
    name = _text(source, 'profile_name')
    if not name or len(name) > 120:
        raise ValueError('Resource Profile name is required and must be at most 120 characters.')
    if TenantResourceProfile.query.filter(func.lower(TenantResourceProfile.name) == name.lower()).first() is not None:
        raise ValueError('A Resource Profile with this name already exists.')

    profile_class = _text(source, 'profile_class').lower()
    if profile_class not in _ALLOWED_PROFILE_CLASSES:
        raise ValueError('Select a supported Resource Profile class.')

    quota, limits = profile_values(profile_class, source)
    profile = TenantResourceProfile()
    profile.name = name
    profile.profile_class = profile_class
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
        raise ValueError('This integration slice can provision only Native Kubernetes Tenant bindings.')

    namespace = _text(source, 'namespace')
    if TenantNamespace.query.filter_by(cluster_id=tenant.cluster_id, namespace=namespace).first() is not None:
        raise ValueError('This namespace is already tracked by Tenant Management on the selected cluster.')

    record = create_namespace_intent(
        tenant_environment=environment,
        profile=profile,
        namespace=namespace,
    )
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


def _shared_context() -> dict[str, Any]:
    ready_clusters = get_ready_native_clusters()
    return {
        'ready_clusters': ready_clusters,
        'native_available': bool(ready_clusters),
        'tenant_count': Tenant.query.count(),
        'profile_count': TenantResourceProfile.query.count(),
        'namespace_count': TenantNamespace.query.count(),
        'ready_namespace_count': TenantNamespace.query.filter_by(provisioning_status='ready').count(),
    }


def get_overview_context() -> dict[str, Any]:
    return {
        **_shared_context(),
        'tenants': Tenant.query.order_by(Tenant.created_at.desc()).limit(5).all(),
        'profiles': TenantResourceProfile.query.order_by(TenantResourceProfile.created_at.desc()).limit(5).all(),
        'namespaces': TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).limit(5).all(),
    }


def get_tenants_context() -> dict[str, Any]:
    return {
        **_shared_context(),
        'tenants': Tenant.query.order_by(Tenant.created_at.desc()).limit(5).all(),
    }


def get_resource_profiles_context() -> dict[str, Any]:
    return {
        **_shared_context(),
        'profiles': TenantResourceProfile.query.order_by(TenantResourceProfile.created_at.desc()).limit(5).all(),
        'resource_profile_presets': copy.deepcopy(RESOURCE_PROFILE_PRESETS),
    }


def get_namespace_provisioning_context() -> dict[str, Any]:
    environment_options = (
        TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value)
        .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
        .all()
    )
    return {
        **_shared_context(),
        'environment_options': environment_options,
        'profiles': TenantResourceProfile.query.filter_by(enabled=True).order_by(TenantResourceProfile.name.asc()).all(),
        'namespaces': TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).limit(5).all(),
    }


def get_operations_context(tab: str) -> dict[str, Any]:
    active_tab = tab if tab in _OPERATION_TABS else 'provisioning'
    recent = TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).limit(25).all()
    evidence = [item for item in recent if item.last_reconciled_at is not None][:5]
    findings = [item for item in recent if item.provisioning_status in {'drifted', 'failed'}][:5]
    return {
        **_shared_context(),
        'active_tab': active_tab,
        'recent_namespaces': recent[:5],
        'evidence_records': evidence,
        'drift_records': findings,
    }


def get_tenant_context() -> dict[str, Any]:
    """Backward-compatible context alias for the original #113 UAT surface."""
    return get_overview_context()
