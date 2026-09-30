from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.pagination import paginate_query
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.kubernetes.tenant.allocation_cutover import (
    allocation_control_state,
    build_allocation_cutover_state,
    reconcile_adopted_native_allocation,
)
from app.kubernetes.tenant.capacity_governance import (
    build_capacity_governance_summary,
    enforce_existing_namespace_allocation_preflight,
    enforce_namespace_allocation_preflight,
)
from app.kubernetes.tenant.capsule_tenant import (
    compensate_capsule_tenant_create,
    create_capsule_tenant,
)
from app.kubernetes.tenant.native_provider import (
    NativeKubernetesTenantProvider,
    tenant_workspace_connection_available,
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
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
    TenantResourceProfile,
    TenantResourceProfileClass,
)

_TENANT_SLUG_RE = re.compile(r'[^a-z0-9-]+')
_ALLOWED_ENVIRONMENTS = {item.value for item in TenantEnvironmentName}
_ALLOWED_PROFILE_CLASSES = {item.value for item in TenantResourceProfileClass}
_ALLOWED_TENANT_PROVIDERS = {'native_kubernetes', 'capsule'}

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
    'extra_large': {
        'version': 1,
        'quota': {
            'requests.cpu': '8',
            'limits.cpu': '16',
            'requests.memory': '16Gi',
            'limits.memory': '32Gi',
            'pods': '80',
            'persistentvolumeclaims': '40',
            'requests.storage': '400Gi',
            'services': '40',
            'configmaps': '200',
            'secrets': '200',
        },
        'limits': {
            'default_request': {'cpu': '500m', 'memory': '512Mi'},
            'default': {'cpu': '2', 'memory': '2Gi'},
        },
    },
}

_PROFILE_QUOTA_FIELDS = {
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
_PROFILE_LIMIT_FIELDS = {
    'default_cpu': ('default', 'cpu'),
    'default_memory': ('default', 'memory'),
    'default_request_cpu': ('default_request', 'cpu'),
    'default_request_memory': ('default_request', 'memory'),
}
_CONTROL_TRUE_VALUES = {'1', 'true', 'yes', 'on'}

RESOURCE_PROFILE_ADVANCED_CONTROLS: dict[str, dict[str, Any]] = {
    'ingress': {
        'label': 'Ingress',
        'description': 'Govern Ingress exposure through the canonical Tenant exposure policy.',
        'authority': '#119',
        'providers': {
            'native_kubernetes': ('service_exposure_preflight', 'admission_enforcement'),
            'capsule': ('resource_rules', 'admission_enforcement'),
        },
    },
    'service_exposure': {
        'label': 'Service Exposure',
        'description': 'Govern ClusterIP, NodePort, LoadBalancer, and ExternalName exposure policy.',
        'authority': '#119',
        'providers': {
            'native_kubernetes': ('service_exposure_preflight', 'admission_enforcement'),
            'capsule': ('resource_rules', 'admission_enforcement'),
        },
    },
    'hostname_reservation': {
        'label': 'Hostname Reservation',
        'description': 'Require canonical hostname ownership and collision checks before exposure.',
        'authority': '#119',
        'providers': {
            'native_kubernetes': ('domain_policy_preflight', 'admission_enforcement'),
            'capsule': ('resource_rules', 'admission_enforcement'),
        },
    },
    'managed_tls': {
        'label': 'Managed TLS',
        'description': 'Request the canonical managed TLS capability for the attached placement.',
        'authority': '#118',
        'providers': {
            'native_kubernetes': ('managed_tls',),
            'capsule': ('replication',),
        },
    },
    'managed_registry': {
        'label': 'Managed Registry',
        'description': 'Request managed private-registry credential capability for the placement.',
        'authority': '#118',
        'providers': {
            'native_kubernetes': ('managed_registry',),
            'capsule': ('replication',),
        },
    },
    'capsule_namespace_controls': {
        'label': 'Capsule Namespace Controls',
        'description': 'Request Capsule namespace count/naming and related Tenant namespace controls.',
        'authority': '#121/#124',
        'providers': {
            'capsule': ('namespace_controls',),
        },
    },
    'capsule_resource_rules': {
        'label': 'Capsule Resource Rules',
        'description': 'Request Capsule StorageClass, PriorityClass, registry, ingress, and service rules.',
        'authority': '#121/#124',
        'providers': {
            'capsule': ('resource_rules',),
        },
    },
    'capsule_resource_pools': {
        'label': 'Capsule Resource Pools',
        'description': 'Request Capsule ResourcePool and claim capability.',
        'authority': '#124',
        'providers': {
            'capsule': ('resource_pools',),
        },
    },
    'capsule_replication': {
        'label': 'Capsule Replication',
        'description': 'Request TenantResource / GlobalTenantResource replication capability.',
        'authority': '#124',
        'providers': {
            'capsule': ('replication',),
        },
    },
    'capsule_tenant_cordon': {
        'label': 'Capsule Tenant Cordon',
        'description': 'Request Capsule Tenant/namespace cordon capability.',
        'authority': '#124',
        'providers': {
            'capsule': ('tenant_cordon',),
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
    clusters = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(Cluster.status == ClusterStatus.CONNECTED.value)
        .order_by(Cluster.name.asc())
        .all()
    )
    return [
        cluster
        for cluster in clusters
        if tenant_workspace_connection_available(cluster.kubernetes_connection)
    ]


def create_tenant(source: Mapping[str, Any]) -> tuple[Tenant, TenantEnvironment]:
    name = _text(source, 'name')
    if not name or len(name) > 120:
        raise ValueError('Tenant name is required and must be at most 120 characters.')

    slug = normalize_tenant_slug(_text(source, 'slug') or name)
    environment = _text(source, 'environment').lower()
    if environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError('Select a supported Tenant environment.')

    provider_key = _text(source, 'provider_key').lower() or 'native_kubernetes'
    if provider_key not in _ALLOWED_TENANT_PROVIDERS:
        raise ValueError('Select a supported Tenant provider.')

    cluster_id = _text(source, 'cluster_id')
    cluster = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(
            Cluster.id == cluster_id,
            Cluster.status == ClusterStatus.CONNECTED.value,
        )
        .first()
    )
    if cluster is None or not tenant_workspace_connection_available(cluster.kubernetes_connection):
        raise ValueError('Select a connected Kubernetes cluster with a validated Tenant integration.')

    prior_generations = (
        Tenant.query.filter_by(cluster_id=cluster.id, slug=slug)
        .order_by(Tenant.generation.desc(), Tenant.created_at.desc())
        .all()
    )
    if any(item.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value for item in prior_generations):
        raise ValueError('An active Tenant with this slug already exists on the selected cluster.')
    generation = max((int(item.generation or 1) for item in prior_generations), default=0) + 1

    tenant = Tenant()
    tenant.cluster_id = cluster.id
    tenant.name = name
    tenant.slug = slug
    tenant.generation = generation
    tenant.description = _text(source, 'description') or None
    tenant.lifecycle_status = TenantLifecycleStatus.PENDING.value
    tenant.provider_key = provider_key
    tenant.provider_state = 'native' if provider_key == 'native_kubernetes' else 'capsule_degraded'
    tenant.reconciliation_authority = 'native_kubernetes' if provider_key == 'native_kubernetes' else 'capsule'
    db.session.add(tenant)
    # Flush uniqueness and integrity constraints before any external provider
    # mutation. A failed flush therefore cannot orphan a Capsule Tenant CR.
    db.session.flush()

    tenant_environment = TenantEnvironment()
    tenant_environment.tenant_id = tenant.id
    tenant_environment.environment = environment
    db.session.add(tenant_environment)
    db.session.flush()

    if provider_key == 'native_kubernetes':
        tenant.provider_state = 'native'
        tenant.reconciliation_authority = 'native_kubernetes'
        tenant.provider_reference = None
        tenant.provider_evidence_json = {
            'provider': 'native_kubernetes',
            'readiness': 'ready',
            'connection_id': cluster.kubernetes_connection.id if cluster.kubernetes_connection else None,
            'source': 'kubernetes_connection',
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }
    else:
        result = create_capsule_tenant(
            cluster=cluster,
            tenant_name=slug,
            kaori_tenant_id=tenant.id,
            generation=generation,
            owner_kind=_text(source, 'capsule_owner_kind'),
            owner_name=_text(source, 'capsule_owner_subject'),
        )
        tenant.provider_state = result.provider_state
        tenant.reconciliation_authority = 'capsule'
        tenant.provider_reference = result.provider_reference
        tenant.provider_evidence_json = result.evidence()

    tenant.lifecycle_status = TenantLifecycleStatus.READY.value
    return tenant, tenant_environment


def _capsule_create_cleanup_context(tenant: Tenant | None) -> dict[str, Any] | None:
    if tenant is None or tenant.provider_key != 'capsule':
        return None
    evidence = tenant.provider_evidence_json or {}
    if not bool(evidence.get('created_by_kaori')):
        return None
    api_version = str(evidence.get('provider_api_version') or '').strip()
    reference = str(evidence.get('provider_reference') or tenant.provider_reference or '').strip()
    if not api_version or not reference:
        return None
    return {
        'cluster_id': str(tenant.cluster_id),
        'api_version': api_version,
        'tenant_name': reference,
        'kaori_tenant_id': tenant.id,
        'expected_uid': str(evidence.get('provider_uid') or '').strip() or None,
    }


def _compensate_capsule_create(context: dict[str, Any] | None) -> bool | None:
    if context is None:
        return None
    cluster = db.session.get(Cluster, context['cluster_id'])
    if cluster is None:
        return False
    return compensate_capsule_tenant_create(
        cluster=cluster,
        api_version=context['api_version'],
        tenant_name=context['tenant_name'],
        kaori_tenant_id=context['kaori_tenant_id'],
        expected_uid=context['expected_uid'],
    )


def create_tenant_committed(source: Mapping[str, Any]) -> tuple[Tenant, TenantEnvironment]:
    tenant: Tenant | None = None
    try:
        tenant, environment = create_tenant(source)
        db.session.commit()
        return tenant, environment
    except ValueError:
        cleanup_context = _capsule_create_cleanup_context(tenant)
        db.session.rollback()
        _compensate_capsule_create(cleanup_context)
        raise
    except IntegrityError as exc:
        cleanup_context = _capsule_create_cleanup_context(tenant)
        db.session.rollback()
        cleaned = _compensate_capsule_create(cleanup_context)
        detail = (
            ' Capsule provider compensation succeeded.'
            if cleaned is True
            else ' Capsule provider compensation could not be verified.'
            if cleaned is False
            else ''
        )
        raise TenantStateConflictError(
            'Committed Tenant state changed while this request was being applied. Refresh and retry.' + detail
        ) from exc
    except SQLAlchemyError:
        cleanup_context = _capsule_create_cleanup_context(tenant)
        db.session.rollback()
        _compensate_capsule_create(cleanup_context)
        raise


def _control_contract_present(source: Mapping[str, Any]) -> bool:
    return _text(source, 'control_contract_present').lower() in _CONTROL_TRUE_VALUES


def _control_enabled(source: Mapping[str, Any], field: str) -> bool:
    if not _control_contract_present(source):
        return True
    return _text(source, f'control_{field}').lower() in _CONTROL_TRUE_VALUES


def _advanced_control_contract_present(source: Mapping[str, Any]) -> bool:
    return _text(source, 'advanced_control_contract_present').lower() in _CONTROL_TRUE_VALUES


def _advanced_profile_controls(source: Mapping[str, Any]) -> dict[str, bool]:
    if not _advanced_control_contract_present(source):
        return {}
    return {
        key: _text(source, f'advanced_control_{key}').lower() in _CONTROL_TRUE_VALUES
        for key in RESOURCE_PROFILE_ADVANCED_CONTROLS
    }


def evaluate_resource_profile_advanced_controls(
    controls: Mapping[str, Any] | None,
    *,
    provider_key: str,
    capability_statuses: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    statuses = {str(key): str(value) for key, value in dict(capability_statuses or {}).items()}
    requested_controls = dict(controls or {})
    result: dict[str, dict[str, Any]] = {}

    for key, contract in RESOURCE_PROFILE_ADVANCED_CONTROLS.items():
        requested = bool(requested_controls.get(key))
        provider_requirements = dict(contract.get('providers') or {}).get(provider_key)
        if not requested:
            state = 'disabled'
            reason = 'Not enabled in this Resource Profile.'
        elif provider_requirements is None:
            state = 'unsupported'
            reason = f'{contract["label"]} is not supported by the {provider_key.replace("_", " ")} placement.'
        else:
            unavailable = [
                capability
                for capability in provider_requirements
                if statuses.get(capability) != 'available'
            ]
            if unavailable:
                state = 'unsupported'
                reason = 'Required provider capability unavailable: ' + ', '.join(unavailable) + '.'
            else:
                state = 'enabled'
                reason = 'Requested by profile and supported by committed provider capability evidence.'

        result[key] = {
            'key': key,
            'label': contract['label'],
            'description': contract['description'],
            'authority': contract['authority'],
            'requested': requested,
            'state': state,
            'reason': reason,
        }
    return result


def _tenant_capability_statuses(tenant: Tenant) -> dict[str, str]:
    if tenant.provider_key == 'native_kubernetes':
        cluster = db.session.get(Cluster, tenant.cluster_id)
        connection = cluster.kubernetes_connection if cluster is not None else None
        if connection is None:
            return {}
        try:
            provider = NativeKubernetesTenantProvider(connection=connection)
            return {
                item.key: item.status.value
                for item in provider.capabilities(cluster_id=str(tenant.cluster_id))
            }
        except Exception:
            return {}

    evidence = tenant.provider_evidence_json or {}
    capsule = evidence.get('capsule') if isinstance(evidence, Mapping) else None
    capsule = capsule if isinstance(capsule, Mapping) else evidence
    capabilities = capsule.get('capabilities') if isinstance(capsule, Mapping) else {}
    return {
        str(key): str(value)
        for key, value in dict(capabilities or {}).items()
    }


def resource_profile_attachment_controls(
    profile: TenantResourceProfile,
    tenant: Tenant,
) -> dict[str, dict[str, Any]]:
    return evaluate_resource_profile_advanced_controls(
        profile.advanced_controls_json or {},
        provider_key=tenant.provider_key,
        capability_statuses=_tenant_capability_statuses(tenant),
    )


def _validate_resource_profile_attachment_controls(
    profile: TenantResourceProfile,
    tenant: Tenant,
) -> dict[str, dict[str, Any]]:
    evaluation = resource_profile_attachment_controls(profile, tenant)
    unsupported = [
        item['label']
        for item in evaluation.values()
        if item['requested'] and item['state'] == 'unsupported'
    ]
    if unsupported:
        raise ValueError(
            'Resource Profile advanced controls are unavailable on the selected provider placement: '
            + ', '.join(unsupported)
            + '.'
        )
    return evaluation


def _profile_values(source: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    quota = {
        target: value
        for field, target in _PROFILE_QUOTA_FIELDS.items()
        if _control_enabled(source, field) and (value := _text(source, field))
    }

    limits: dict[str, dict[str, str]] = {}
    for field, (group, resource) in _PROFILE_LIMIT_FIELDS.items():
        value = _text(source, field)
        if _control_enabled(source, field) and value:
            limits.setdefault(group, {})[resource] = value

    return validate_profile_spec(quota, limits)


def _preset_controlled_values(
    preset: Mapping[str, Any],
    source: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    if not _control_contract_present(source):
        return validate_profile_spec(preset['quota'], preset['limits'])

    quota = {
        target: preset['quota'][target]
        for field, target in _PROFILE_QUOTA_FIELDS.items()
        if _control_enabled(source, field) and target in preset['quota']
    }
    limits: dict[str, dict[str, str]] = {}
    for field, (group, resource) in _PROFILE_LIMIT_FIELDS.items():
        if not _control_enabled(source, field):
            continue
        value = (preset['limits'].get(group) or {}).get(resource)
        if value:
            limits.setdefault(group, {})[resource] = value

    return validate_profile_spec(quota, limits)


def _resource_profile_values(
    profile_class: str,
    source: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, str]], int, str | None, int | None]:
    if profile_class in RESOURCE_PROFILE_PRESETS:
        preset = RESOURCE_PROFILE_PRESETS[profile_class]
        quota, limits = _preset_controlled_values(preset, source)
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
        stored_quota = profile.quota_hard_json or {}
        stored_limits = profile.limit_defaults_json or {}
        quota = {
            key: preset['quota'][key]
            for key in stored_quota
            if key in preset['quota']
        }
        limits: dict[str, dict[str, str]] = {}
        for group, resources in stored_limits.items():
            preset_group = preset['limits'].get(group) or {}
            for resource in (resources or {}):
                if resource in preset_group:
                    limits.setdefault(group, {})[resource] = preset_group[resource]
        quota, limits = validate_profile_spec(quota, limits)
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
    profile.advanced_controls_json = _advanced_profile_controls(source)
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


def _resource_profile_dependency_counts(profile_id: int) -> dict[str, int]:
    namespace_count = TenantNamespace.query.filter_by(resource_profile_id=profile_id).count()
    capacity_decision_count = TenantCapacityDecision.query.filter_by(resource_profile_id=profile_id).count()
    return {
        'namespaces': namespace_count,
        'capacity_decisions': capacity_decision_count,
        'total': namespace_count + capacity_decision_count,
    }


def update_resource_profile(profile_id: int, source: Mapping[str, Any]) -> tuple[TenantResourceProfile, bool]:
    profile = db.session.get(TenantResourceProfile, profile_id)
    if profile is None:
        raise ValueError('Selected Resource Profile no longer exists.')
    if profile.profile_class != TenantResourceProfileClass.CUSTOM.value:
        raise ValueError('Built-in Resource Profiles are locked. Create or edit a Custom profile instead.')

    name = _text(source, 'profile_name')
    if not name or len(name) > 120:
        raise ValueError('Resource Profile name is required and must be at most 120 characters.')
    duplicate = TenantResourceProfile.query.filter(
        func.lower(TenantResourceProfile.name) == name.lower(),
        TenantResourceProfile.id != profile.id,
    ).first()
    if duplicate is not None:
        raise ValueError('A Resource Profile with this name already exists.')

    enabled_value = _text(source, 'profile_enabled').lower()
    if enabled_value not in {'enabled', 'disabled'}:
        raise ValueError('Select whether the Custom Resource Profile is Enabled or Disabled.')

    quota, limits = _profile_values(source)
    advanced_controls = _advanced_profile_controls(source)
    contract_changed = (
        quota != (profile.quota_hard_json or {})
        or limits != (profile.limit_defaults_json or {})
        or advanced_controls != (profile.advanced_controls_json or {})
    )

    profile.name = name
    profile.description = _text(source, 'profile_description') or None
    profile.quota_hard_json = quota
    profile.limit_defaults_json = limits
    profile.advanced_controls_json = advanced_controls
    profile.enabled = enabled_value == 'enabled'
    if contract_changed:
        profile.version = int(profile.version or 1) + 1

    db.session.flush()
    return profile, contract_changed


def update_resource_profile_committed(
    profile_id: int,
    source: Mapping[str, Any],
) -> tuple[TenantResourceProfile, bool]:
    try:
        result = update_resource_profile(profile_id, source)
        db.session.commit()
        return result
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed Resource Profile state changed while this update was being applied. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_resource_profile(profile_id: int) -> dict[str, Any]:
    profile = db.session.get(TenantResourceProfile, profile_id)
    if profile is None:
        raise ValueError('Selected Resource Profile no longer exists.')
    if profile.profile_class != TenantResourceProfileClass.CUSTOM.value:
        raise ValueError('Built-in Resource Profiles are KAORI-owned and cannot be deleted.')

    dependencies = _resource_profile_dependency_counts(profile.id)
    if dependencies['total']:
        raise ValueError(
            'Delete blocked: release all Resource Profile dependencies first. '
            f'{dependencies["namespaces"]} Namespace reference(s) and '
            f'{dependencies["capacity_decisions"]} Capacity Decision reference(s) remain.'
        )

    snapshot = {
        'id': profile.id,
        'public_id': profile.public_id,
        'name': profile.name,
        'profile_class': profile.profile_class,
        'version': profile.version,
    }
    db.session.delete(profile)
    db.session.flush()
    return snapshot


def delete_resource_profile_committed(profile_id: int) -> dict[str, Any]:
    try:
        result = delete_resource_profile(profile_id)
        db.session.commit()
        return result
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Resource Profile dependencies changed while deletion was being applied. Refresh and retry.'
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
    prior_namespace_generations = (
        TenantNamespace.query.filter_by(cluster_id=tenant.cluster_id, namespace=namespace)
        .order_by(TenantNamespace.generation.desc(), TenantNamespace.created_at.desc())
        .all()
    )
    if any(
        item.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
        for item in prior_namespace_generations
    ):
        raise ValueError('This namespace is already active in Tenant Management on the selected cluster.')
    namespace_generation = (
        max(
            (int(item.generation or 1) for item in prior_namespace_generations),
            default=0,
        )
        + 1
    )

    attachment_controls = _validate_resource_profile_attachment_controls(profile, tenant)
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
    record.generation = namespace_generation
    try:
        reconcile_native_namespace(record)
    except (ApiException, ValueError):
        db.session.commit()
        raise

    provisioning_evidence = dict(record.provisioning_evidence_json or {})
    provisioning_evidence['advanced_profile_controls'] = {
        'source_profile_id': profile.public_id,
        'source_profile_version': int(profile.version or 1),
        'provider_key': tenant.provider_key,
        'controls': attachment_controls,
    }
    record.provisioning_evidence_json = provisioning_evidence
    db.session.commit()

    # Explicit namespace provisioning may expand previously committed
    # Environment/Tenant access scopes. Reconcile those grants after the
    # namespace itself is safely committed; inventory/sync remains observation-only.
    from app.kubernetes.tenant.access_service import reconcile_access_grants_for_namespace_committed

    access_followup = reconcile_access_grants_for_namespace_committed(namespace=record)
    evidence = dict(record.provisioning_evidence_json or {})
    evidence['access_grant_followup'] = {
        **access_followup,
        'trigger': 'explicit_namespace_provision',
        'namespace': record.namespace,
    }
    record.provisioning_evidence_json = evidence
    if access_followup['matched']:
        record.provisioning_message = (
            f'{record.provisioning_message or ""} '
            f'Access Grant follow-up: {access_followup["reconciled"]} reconciled'
            f'; {access_followup["failed"]} require attention.'
        ).strip()
    db.session.commit()
    return record


def change_native_namespace_allocation(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        namespace_id = int(_text(source, 'tenant_namespace_id'))
        profile_id = int(_text(source, 'resource_profile_id'))
    except ValueError as exc:
        raise ValueError('Select a managed Tenant namespace and Resource Profile.') from exc

    record = db.session.get(TenantNamespace, namespace_id)
    profile = db.session.get(TenantResourceProfile, profile_id)
    if record is None:
        raise ValueError('Selected Tenant namespace no longer exists.')
    if profile is None or not profile.enabled:
        raise ValueError('Selected Resource Profile is unavailable.')
    if record.environment.tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant is not Ready; namespace allocation changes are frozen during decommission.')
    if record.environment.tenant.provider_key != 'native_kubernetes':
        raise ValueError('This UAT slice can change only Native Kubernetes Tenant allocations.')
    if allocation_control_state(record) != 'kaori_managed':
        raise ValueError(
            'Adopted Baseline allocations are read-only until explicit Allocation Governance Cutover is completed.'
        )

    attachment_controls = _validate_resource_profile_attachment_controls(profile, record.environment.tenant)
    quota, limits, customized = _namespace_allocation_values(profile)
    capacity_decision = enforce_existing_namespace_allocation_preflight(
        record=record,
        profile=profile,
        quota_hard=quota,
    )

    profile_version = (
        int(RESOURCE_PROFILE_PRESETS[profile.profile_class]['version'])
        if profile.profile_class in RESOURCE_PROFILE_PRESETS
        else profile.version
    )

    try:
        if record.ownership_status == TenantOwnershipStatus.ADOPTED.value:
            reconcile_adopted_native_allocation(
                record,
                profile=profile,
                resource_profile_version=profile_version,
                allocation_customized=customized,
                capacity_decision_id=capacity_decision.id,
                quota_hard=quota,
                limit_defaults=limits,
                operation='allocation_change',
            )
        else:
            record.resource_profile = profile
            record.resource_profile_id = profile.id
            record.resource_profile_version = profile_version
            record.allocation_quota_json = quota
            record.allocation_limit_defaults_json = limits
            record.allocation_customized = customized
            record.capacity_decision_id = capacity_decision.id
            reconcile_native_namespace(record)
    except (ApiException, ValueError):
        db.session.commit()
        raise
    evidence = dict(record.provisioning_evidence_json or {})
    evidence['advanced_profile_controls'] = {
        'source_profile_id': profile.public_id,
        'source_profile_version': int(profile.version or 1),
        'provider_key': record.environment.tenant.provider_key,
        'controls': attachment_controls,
    }
    record.provisioning_evidence_json = evidence
    db.session.commit()
    return record


def change_native_namespace_allocation_committed(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        return change_native_namespace_allocation(source)
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed Tenant namespace allocation changed while this request was being applied. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def cutover_adopted_namespace_allocation(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        namespace_id = int(_text(source, 'tenant_namespace_id'))
        profile_id = int(_text(source, 'resource_profile_id'))
    except ValueError as exc:
        raise ValueError('Select an adopted Tenant namespace and Resource Profile for governance cutover.') from exc

    record = db.session.get(TenantNamespace, namespace_id)
    profile = db.session.get(TenantResourceProfile, profile_id)
    if record is None:
        raise ValueError('Selected Tenant namespace no longer exists.')
    if profile is None or not profile.enabled:
        raise ValueError('Selected Resource Profile is unavailable.')
    if record.environment.tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant is not Ready; allocation governance cutover is unavailable during teardown.')

    cutover = build_allocation_cutover_state(record)
    if not cutover['supported']:
        raise ValueError(str(cutover['reason']))

    attachment_controls = _validate_resource_profile_attachment_controls(profile, record.environment.tenant)
    quota, limits, customized = _namespace_allocation_values(profile)
    capacity_decision = enforce_existing_namespace_allocation_preflight(
        record=record,
        profile=profile,
        quota_hard=quota,
    )
    profile_version = (
        int(RESOURCE_PROFILE_PRESETS[profile.profile_class]['version'])
        if profile.profile_class in RESOURCE_PROFILE_PRESETS
        else profile.version
    )

    try:
        reconcile_adopted_native_allocation(
            record,
            profile=profile,
            resource_profile_version=profile_version,
            allocation_customized=customized,
            capacity_decision_id=capacity_decision.id,
            quota_hard=quota,
            limit_defaults=limits,
            operation='allocation_governance_cutover',
        )
    except (ApiException, ValueError):
        db.session.commit()
        raise
    evidence = dict(record.provisioning_evidence_json or {})
    evidence['advanced_profile_controls'] = {
        'source_profile_id': profile.public_id,
        'source_profile_version': int(profile.version or 1),
        'provider_key': record.environment.tenant.provider_key,
        'controls': attachment_controls,
    }
    record.provisioning_evidence_json = evidence
    db.session.commit()
    return record


def cutover_adopted_namespace_allocation_committed(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        return cutover_adopted_namespace_allocation(source)
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed adopted allocation changed while governance cutover was being applied. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


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


def reconcile_managed_native_namespace_committed(*, namespace_id: int) -> TenantNamespace:
    record = db.session.get(TenantNamespace, namespace_id)
    if record is None:
        raise ValueError('Selected Tenant namespace no longer exists.')

    tenant = record.environment.tenant
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant is not Ready; namespace reconciliation is unavailable during teardown.')
    if record.provisioning_status != TenantNamespaceProvisioningStatus.DRIFTED.value:
        raise ValueError('Namespace must be in Drifted state before explicit provider reconciliation.')
    if record.ownership_status != TenantOwnershipStatus.MANAGED.value:
        raise ValueError(
            'Only KAORI-managed namespaces can be recreated from committed intent. '
            'Adopted namespaces require provider restoration or governed review.'
        )
    if tenant.provider_key != 'native_kubernetes' or tenant.reconciliation_authority != 'native_kubernetes':
        raise ValueError('Explicit namespace recreation requires Native Kubernetes reconciliation authority.')

    try:
        reconcile_native_namespace(record)
        db.session.commit()
        return record
    except (ApiException, ValueError):
        # Preserve reconciliation evidence emitted by the provider adapter.
        db.session.commit()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantStateConflictError(
            'Committed Tenant namespace state changed during reconciliation. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


_ALLOWED_PAGE_SIZES = (5, 10, 25, 50)


def _paged_context(query: Any, *, page: int, per_page: int) -> tuple[list[Any], dict[str, Any]]:
    normalized_page = max(int(page), 1)
    normalized_per_page = per_page if per_page in _ALLOWED_PAGE_SIZES else 5
    pagination = query.paginate(page=normalized_page, per_page=normalized_per_page, error_out=False)
    if pagination.pages and normalized_page > pagination.pages:
        normalized_page = pagination.pages
        pagination = query.paginate(page=normalized_page, per_page=normalized_per_page, error_out=False)

    start_item = ((normalized_page - 1) * normalized_per_page + 1) if pagination.total else 0
    end_item = min(normalized_page * normalized_per_page, pagination.total) if pagination.total else 0
    return list(pagination.items), {
        'page': normalized_page,
        'per_page': normalized_per_page,
        'total': pagination.total,
        'pages': max(pagination.pages, 1),
        'start_item': start_item,
        'end_item': end_item,
        'has_prev': pagination.has_prev,
        'prev_num': pagination.prev_num,
        'has_next': pagination.has_next,
        'next_num': pagination.next_num,
        'allowed_per_page': _ALLOWED_PAGE_SIZES,
    }


def get_tenant_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    cluster_id: str = '',
    environment: str = '',
    lifecycle_status: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_cluster_id = cluster_id.strip()
    normalized_environment = environment.strip().lower()
    normalized_lifecycle = lifecycle_status.strip().lower()

    query = Tenant.query

    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(Tenant.name).like(pattern),
                func.lower(Tenant.slug).like(pattern),
            )
        )
    if normalized_cluster_id:
        query = query.filter(Tenant.cluster_id == normalized_cluster_id)
    if normalized_lifecycle:
        query = query.filter(Tenant.lifecycle_status == normalized_lifecycle)
    if normalized_environment:
        query = (
            query.join(TenantEnvironment, TenantEnvironment.tenant_id == Tenant.id)
            .filter(TenantEnvironment.environment == normalized_environment)
            .distinct()
        )

    items, pagination = paginate_query(
        query.order_by(Tenant.created_at.desc(), Tenant.name.asc()),
        page=page,
        per_page=per_page,
    )

    tenant_ids = [item.id for item in items]
    environment_map: dict[str, list[str]] = {tenant_id: [] for tenant_id in tenant_ids}
    namespace_count_map: dict[str, int] = {tenant_id: 0 for tenant_id in tenant_ids}
    namespace_history_count_map: dict[str, int] = {tenant_id: 0 for tenant_id in tenant_ids}

    if tenant_ids:
        environment_rows = (
            TenantEnvironment.query.filter(TenantEnvironment.tenant_id.in_(tenant_ids))
            .order_by(TenantEnvironment.tenant_id.asc(), TenantEnvironment.environment.asc())
            .all()
        )
        for row in environment_rows:
            environment_map.setdefault(row.tenant_id, []).append(row.environment)

        namespace_history_rows = (
            db.session.query(TenantEnvironment.tenant_id, func.count(TenantNamespace.id))
            .join(TenantNamespace, TenantNamespace.tenant_environment_id == TenantEnvironment.id)
            .filter(TenantEnvironment.tenant_id.in_(tenant_ids))
            .group_by(TenantEnvironment.tenant_id)
            .all()
        )
        namespace_history_count_map.update({str(tenant_id): int(count) for tenant_id, count in namespace_history_rows})

        namespace_rows = (
            db.session.query(TenantEnvironment.tenant_id, func.count(TenantNamespace.id))
            .join(TenantNamespace, TenantNamespace.tenant_environment_id == TenantEnvironment.id)
            .filter(
                TenantEnvironment.tenant_id.in_(tenant_ids),
                TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
            )
            .group_by(TenantEnvironment.tenant_id)
            .all()
        )
        namespace_count_map.update({str(tenant_id): int(count) for tenant_id, count in namespace_rows})

    cluster_ids = {item.cluster_id for item in items}
    cluster_map = (
        {str(cluster.id): cluster for cluster in Cluster.query.filter(Cluster.id.in_(cluster_ids)).all()}
        if cluster_ids
        else {}
    )

    from app.kubernetes.tenant.decommission_service import build_tenant_decommission_preflight

    tenant_rows = [
        {
            'tenant': item,
            'cluster': cluster_map.get(str(item.cluster_id)),
            'environments': environment_map.get(item.id, []),
            'namespace_count': namespace_count_map.get(item.id, 0),
            'namespace_history_count': namespace_history_count_map.get(item.id, 0),
            'decommission_preflight': build_tenant_decommission_preflight(item.id),
        }
        for item in items
    ]

    return {
        'tenants': items,
        'tenant_rows': tenant_rows,
        'tenant_pagination': pagination,
        'tenant_registry_filters': {
            'search': normalized_search,
            'cluster_id': normalized_cluster_id,
            'environment': normalized_environment,
            'lifecycle_status': normalized_lifecycle,
        },
        'tenant_cluster_options': Cluster.query.order_by(Cluster.name.asc()).all(),
        'tenant_environment_filter_options': [item.value for item in TenantEnvironmentName],
        'tenant_lifecycle_filter_options': [item.value for item in TenantLifecycleStatus],
    }


def get_resource_profile_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    profile_class: str = '',
    state: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_class = profile_class.strip().lower()
    normalized_state = state.strip().lower()

    query = TenantResourceProfile.query
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantResourceProfile.name).like(pattern),
                func.lower(func.coalesce(TenantResourceProfile.description, '')).like(pattern),
            )
        )
    if normalized_class in _ALLOWED_PROFILE_CLASSES:
        query = query.filter(TenantResourceProfile.profile_class == normalized_class)
    else:
        normalized_class = ''
    if normalized_state == 'enabled':
        query = query.filter(TenantResourceProfile.enabled.is_(True))
    elif normalized_state == 'disabled':
        query = query.filter(TenantResourceProfile.enabled.is_(False))
    else:
        normalized_state = ''

    items, pagination = paginate_query(
        query.order_by(TenantResourceProfile.created_at.desc(), TenantResourceProfile.name.asc()),
        page=page,
        per_page=per_page,
    )

    profile_ids = [profile.id for profile in items]
    namespace_counts: dict[int, int] = {}
    capacity_decision_counts: dict[int, int] = {}
    if profile_ids:
        namespace_counts = {
            int(profile_id): int(count)
            for profile_id, count in (
                db.session.query(TenantNamespace.resource_profile_id, func.count(TenantNamespace.id))
                .filter(TenantNamespace.resource_profile_id.in_(profile_ids))
                .group_by(TenantNamespace.resource_profile_id)
                .all()
            )
            if profile_id is not None
        }
        capacity_decision_counts = {
            int(profile_id): int(count)
            for profile_id, count in (
                db.session.query(TenantCapacityDecision.resource_profile_id, func.count(TenantCapacityDecision.id))
                .filter(TenantCapacityDecision.resource_profile_id.in_(profile_ids))
                .group_by(TenantCapacityDecision.resource_profile_id)
                .all()
            )
            if profile_id is not None
        }

    profile_dependencies = {
        profile.id: {
            'namespaces': namespace_counts.get(profile.id, 0),
            'capacity_decisions': capacity_decision_counts.get(profile.id, 0),
            'total': namespace_counts.get(profile.id, 0) + capacity_decision_counts.get(profile.id, 0),
        }
        for profile in items
    }

    return {
        'profiles': items,
        'profile_dependencies': profile_dependencies,
        'profile_pagination': pagination,
        'profile_registry_filters': {
            'search': normalized_search,
            'profile_class': normalized_class,
            'state': normalized_state,
        },
        'profile_class_filter_options': [item.value for item in TenantResourceProfileClass],
    }


def get_capacity_decision_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    decision: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_decision = decision.strip().lower()

    query = (
        db.session.query(TenantCapacityDecision, Cluster, TenantResourceProfile)
        .join(
            Cluster,
            Cluster.id == TenantCapacityDecision.cluster_id,
        )
        .outerjoin(
            TenantResourceProfile,
            TenantResourceProfile.id == TenantCapacityDecision.resource_profile_id,
        )
    )
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantCapacityDecision.namespace).like(pattern),
                func.lower(Cluster.name).like(pattern),
                func.lower(Cluster.environment).like(pattern),
                func.lower(TenantCapacityDecision.operation).like(pattern),
                func.lower(TenantCapacityDecision.capacity_state).like(pattern),
                func.lower(TenantResourceProfile.name).like(pattern),
            )
        )

    if normalized_decision in {'allow', 'block'}:
        query = query.filter(TenantCapacityDecision.decision == normalized_decision)
    else:
        normalized_decision = ''

    items, pagination = paginate_query(
        query.order_by(TenantCapacityDecision.created_at.desc(), TenantCapacityDecision.id.desc()),
        page=page,
        per_page=per_page,
    )

    return {
        'capacity_decision_rows': [
            {
                'decision': decision_row,
                'cluster': cluster,
                'profile': profile,
                'created_at_label': present_user_datetime(decision_row.created_at, empty='—'),
                'data_cutoff_label': present_user_datetime(decision_row.data_cutoff, empty='No cutoff'),
            }
            for decision_row, cluster, profile in items
        ],
        'capacity_decision_pagination': pagination,
        'capacity_decision_filters': {
            'search': normalized_search,
            'decision': normalized_decision,
        },
    }


def get_namespace_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    tenant_id: str = '',
    environment: str = '',
    status: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_tenant_id = tenant_id.strip()
    normalized_environment = environment.strip().lower()
    normalized_status = status.strip().lower()
    allowed_statuses = {item.value for item in TenantNamespaceProvisioningStatus}

    query = TenantNamespace.query.join(
        TenantEnvironment,
        TenantNamespace.tenant_environment_id == TenantEnvironment.id,
    ).join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantNamespace.namespace).like(pattern),
                func.lower(Tenant.name).like(pattern),
                func.lower(Tenant.slug).like(pattern),
            )
        )
    if normalized_tenant_id:
        query = query.filter(Tenant.id == normalized_tenant_id)
    if normalized_environment in _ALLOWED_ENVIRONMENTS:
        query = query.filter(TenantEnvironment.environment == normalized_environment)
    else:
        normalized_environment = ''
    if normalized_status in allowed_statuses:
        query = query.filter(TenantNamespace.provisioning_status == normalized_status)
    else:
        normalized_status = ''

    items, pagination = paginate_query(
        query.order_by(TenantNamespace.created_at.desc(), TenantNamespace.id.desc()),
        page=page,
        per_page=per_page,
    )

    namespace_options = TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).all()
    namespace_allocation_options = [
        record
        for record in namespace_options
        if allocation_control_state(record) == 'kaori_managed'
        and record.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
    ]
    namespace_cutover_options = [
        record
        for record in namespace_options
        if record.ownership_status == TenantOwnershipStatus.ADOPTED.value
        and allocation_control_state(record) != 'kaori_managed'
        and record.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
    ]
    namespace_cutover_state = {
        str(record.id): build_allocation_cutover_state(record) for record in namespace_cutover_options
    }
    profile_options = (
        TenantResourceProfile.query.filter_by(enabled=True).order_by(TenantResourceProfile.name.asc()).all()
    )
    tenant_options = (
        Tenant.query.filter(Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value)
        .order_by(Tenant.name.asc())
        .all()
    )
    return {
        'namespaces': items,
        'namespace_options': namespace_options,
        'namespace_allocation_options': namespace_allocation_options,
        'namespace_cutover_options': namespace_cutover_options,
        'namespace_cutover_state': namespace_cutover_state,
        'namespace_cutover_supported': any(item['supported'] for item in namespace_cutover_state.values()),
        'profiles': profile_options,
        'namespace_pagination': pagination,
        'namespace_registry_filters': {
            'search': normalized_search,
            'tenant_id': normalized_tenant_id,
            'environment': normalized_environment,
            'status': normalized_status,
        },
        'namespace_registry_tenant_options': tenant_options,
        'namespace_status_filter_options': [item.value for item in TenantNamespaceProvisioningStatus],
        'namespace_environment_filter_options': sorted(_ALLOWED_ENVIRONMENTS),
        'namespace_allocation_state': {
            str(record.id): {
                'namespace': record.namespace,
                'profile_id': str(record.resource_profile_id) if record.resource_profile_id is not None else None,
                'profile_name': (
                    record.resource_profile.name
                    if record.resource_profile is not None
                    else str(
                        (
                            (
                                (record.provisioning_evidence_json or {}).get('allocation')
                                if isinstance((record.provisioning_evidence_json or {}).get('allocation'), dict)
                                else {}
                            ).get('profile_lineage')
                            or {}
                        ).get('label')
                        or 'Adopted Baseline · Observed'
                    )
                ),
                'profile_version': (
                    record.resource_profile_version
                    or (
                        (
                            (
                                (record.provisioning_evidence_json or {}).get('allocation')
                                if isinstance((record.provisioning_evidence_json or {}).get('allocation'), dict)
                                else {}
                            ).get('profile_lineage')
                            or {}
                        ).get('profile_version')
                    )
                ),
                'quota': record.allocation_quota_json or {},
                'limits': record.allocation_limit_defaults_json or {},
                'control_state': allocation_control_state(record),
            }
            for record in namespace_options
        },
        'namespace_allocation_profiles': {
            str(profile.id): {
                'quota': profile.quota_hard_json or {},
                'limits': profile.limit_defaults_json or {},
                'version': (
                    int(RESOURCE_PROFILE_PRESETS[profile.profile_class]['version'])
                    if profile.profile_class in RESOURCE_PROFILE_PRESETS
                    else profile.version
                ),
                'profile_class': profile.profile_class,
                'advanced_controls': profile.advanced_controls_json or {},
            }
            for profile in profile_options
        },
    }


def get_tenant_context() -> dict[str, Any]:
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).limit(5).all()
    profiles = TenantResourceProfile.query.order_by(TenantResourceProfile.created_at.desc()).limit(5).all()
    namespaces = TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).limit(5).all()
    environment_options = (
        TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(Tenant.lifecycle_status == TenantLifecycleStatus.READY.value)
        .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
        .all()
    )
    ready_clusters = get_ready_native_clusters()
    registered_clusters = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .order_by(Cluster.name.asc(), Cluster.id.asc())
        .all()
    )
    capacity_governance = [
        {'cluster': cluster, **build_capacity_governance_summary(cluster.id)} for cluster in registered_clusters
    ]
    capacity_decisions = TenantCapacityDecision.query.order_by(TenantCapacityDecision.created_at.desc()).limit(5).all()
    namespace_count = TenantNamespace.query.filter(TenantNamespace.provisioning_status != 'deprovisioned').count()
    profile_count = TenantResourceProfile.query.count()
    enabled_profile_count = TenantResourceProfile.query.filter_by(enabled=True).count()
    custom_profile_count = TenantResourceProfile.query.filter_by(
        profile_class=TenantResourceProfileClass.CUSTOM.value
    ).count()
    active_profile_allocation_count = TenantNamespace.query.filter(
        TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        TenantNamespace.resource_profile_id.isnot(None),
    ).count()
    return {
        'tenants': tenants,
        'profiles': profiles,
        'namespaces': namespaces,
        'environment_options': environment_options,
        'ready_clusters': ready_clusters,
        'registered_clusters': registered_clusters,
        'capacity_governance': capacity_governance,
        'capacity_policy_state': {
            str(item['cluster'].id): item['policy'] for item in capacity_governance if item.get('policy') is not None
        },
        'capacity_decisions': capacity_decisions,
        'tenant_count': Tenant.query.filter(
            Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value
        ).count(),
        'profile_count': profile_count,
        'resource_profile_stats': {
            'total': profile_count,
            'enabled': enabled_profile_count,
            'custom': custom_profile_count,
            'active_allocations': active_profile_allocation_count,
        },
        'namespace_count': namespace_count,
        'ready_namespace_count': TenantNamespace.query.filter_by(provisioning_status='ready').count(),
        'namespace_drift_rows': (
            TenantNamespace.query.filter_by(provisioning_status=TenantNamespaceProvisioningStatus.DRIFTED.value)
            .order_by(TenantNamespace.updated_at.desc(), TenantNamespace.id.desc())
            .limit(20)
            .all()
        ),
        'native_available': bool(ready_clusters),
        'resource_profile_presets': RESOURCE_PROFILE_PRESETS,
        'resource_profile_advanced_controls': RESOURCE_PROFILE_ADVANCED_CONTROLS,
        'tenant_environment_advanced_control_state': {
            str(environment.id): {
                'tenant_id': environment.tenant_id,
                'provider_key': environment.tenant.provider_key,
                'provider_state': environment.tenant.provider_state,
                'controls': evaluate_resource_profile_advanced_controls(
                    {key: True for key in RESOURCE_PROFILE_ADVANCED_CONTROLS},
                    provider_key=environment.tenant.provider_key,
                    capability_statuses=_tenant_capability_statuses(environment.tenant),
                ),
            }
            for environment in environment_options
        },
        'namespace_allocation_state': {
            str(record.id): {
                'namespace': record.namespace,
                'profile_id': str(record.resource_profile_id) if record.resource_profile_id is not None else None,
                'profile_name': record.resource_profile.name if record.resource_profile is not None else 'Unknown',
                'profile_version': record.resource_profile_version,
                'quota': record.allocation_quota_json or {},
                'limits': record.allocation_limit_defaults_json or {},
            }
            for record in namespaces
        },
        'namespace_allocation_profiles': {
            str(profile.id): {
                'quota': profile.quota_hard_json or {},
                'limits': profile.limit_defaults_json or {},
                'version': (
                    int(RESOURCE_PROFILE_PRESETS[profile.profile_class]['version'])
                    if profile.profile_class in RESOURCE_PROFILE_PRESETS
                    else profile.version
                ),
                'profile_class': profile.profile_class,
                'advanced_controls': profile.advanced_controls_json or {},
            }
            for profile in profiles
            if profile.enabled
        },
    }
