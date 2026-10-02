from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.allocation_cutover import (
    allocation_control_state,
    build_allocation_cutover_state,
    reconcile_adopted_native_allocation,
)
from app.kubernetes.tenant.capacity_governance import (
    enforce_existing_namespace_allocation_preflight,
    enforce_namespace_allocation_preflight,
)
from app.kubernetes.tenant.capsule_tenant import (
    compensate_capsule_tenant_create,
    create_capsule_tenant,
)
from app.kubernetes.tenant.native_provider import tenant_workspace_connection_available
from app.kubernetes.tenant.provisioning import create_namespace_intent, reconcile_native_namespace
from app.kubernetes.tenant.resource_profile_controls import (
    _advanced_profile_controls as _advanced_profile_controls,
    _control_contract_present as _control_contract_present,
    _control_enabled as _control_enabled,
    _tenant_capability_statuses as _tenant_capability_statuses,
    _validate_resource_profile_attachment_controls as _validate_resource_profile_attachment_controls,
    _validate_resource_profile_base_controls as _validate_resource_profile_base_controls,
    evaluate_resource_profile_advanced_controls as evaluate_resource_profile_advanced_controls,
    resource_profile_attachment_controls as resource_profile_attachment_controls,
    resource_profile_base_control_state as resource_profile_base_control_state,
)
from app.kubernetes.tenant.registry_context import (
    _resource_profile_rollout_targets as _resource_profile_rollout_targets,
    get_capacity_decision_registry_context as get_capacity_decision_registry_context,
    get_namespace_registry_context as get_namespace_registry_context,
    get_ready_native_clusters as get_ready_native_clusters,
    get_resource_profile_registry_context as get_resource_profile_registry_context,
    get_tenant_context as get_tenant_context,
    get_tenant_registry_context as get_tenant_registry_context,
)
from app.kubernetes.tenant.service_contracts import (
    RESOURCE_PROFILE_ADVANCED_CONTROLS as RESOURCE_PROFILE_ADVANCED_CONTROLS,
    RESOURCE_PROFILE_PRESETS as RESOURCE_PROFILE_PRESETS,
    _ALLOWED_ENVIRONMENTS as _ALLOWED_ENVIRONMENTS,
    _ALLOWED_PROFILE_CLASSES as _ALLOWED_PROFILE_CLASSES,
    _ALLOWED_TENANT_PROVIDERS as _ALLOWED_TENANT_PROVIDERS,
    _CONTROL_TRUE_VALUES as _CONTROL_TRUE_VALUES,
    _PROFILE_LIMIT_FIELDS as _PROFILE_LIMIT_FIELDS,
    _PROFILE_QUOTA_FIELDS as _PROFILE_QUOTA_FIELDS,
    _PROFILE_STORAGE_FIELDS as _PROFILE_STORAGE_FIELDS,
    _TENANT_SLUG_RE as _TENANT_SLUG_RE,
    _text as _text,
)
from app.kubernetes.tenant.validation import validate_profile_spec, validate_storage_policy
from app.models import Cluster
from app.models.cluster import ClusterStatus
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
    TenantCapacityDecision,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
    TenantResourceProfile,
    TenantResourceProfileClass,
)


class TenantStateConflictError(RuntimeError):
    """Committed Tenant state changed while a mutation transaction was applying."""


def normalize_tenant_slug(value: str) -> str:
    slug = _TENANT_SLUG_RE.sub('-', value.strip().lower().replace('_', '-').replace(' ', '-'))
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug or len(slug) > 63:
        raise ValueError('Tenant slug must contain 1–63 lowercase letters, numbers, or hyphens.')
    return slug


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


def _storage_policy_values(source: Mapping[str, Any]) -> dict[str, str]:
    policy = {
        target: value
        for field, target in _PROFILE_STORAGE_FIELDS.items()
        if _control_enabled(source, field) and (value := _text(source, field))
    }
    return validate_storage_policy(policy)


def _preset_storage_policy_values(
    preset: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, str]:
    policy = dict(preset.get('storage_policy') or {})
    if not _control_contract_present(source):
        return validate_storage_policy(policy)
    selected = {
        target: policy[target]
        for field, target in _PROFILE_STORAGE_FIELDS.items()
        if _control_enabled(source, field) and target in policy
    }
    return validate_storage_policy(selected)


def _resource_profile_storage_values(
    profile_class: str,
    source: Mapping[str, Any],
) -> dict[str, str]:
    if profile_class in RESOURCE_PROFILE_PRESETS:
        return _preset_storage_policy_values(RESOURCE_PROFILE_PRESETS[profile_class], source)
    return _storage_policy_values(source)


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
) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str], bool]:
    if profile.profile_class in RESOURCE_PROFILE_PRESETS:
        preset = RESOURCE_PROFILE_PRESETS[profile.profile_class]
        stored_quota = profile.quota_hard_json or {}
        stored_limits = profile.limit_defaults_json or {}
        quota = {key: preset['quota'][key] for key in stored_quota if key in preset['quota']}
        limits: dict[str, dict[str, str]] = {}
        for group, resources in stored_limits.items():
            preset_group = preset['limits'].get(group) or {}
            for resource in resources or {}:
                if resource in preset_group:
                    limits.setdefault(group, {})[resource] = preset_group[resource]
        quota, limits = validate_profile_spec(quota, limits)
        storage_policy = validate_storage_policy(getattr(profile, 'storage_policy_json', {}) or {})
        return quota, limits, storage_policy, False

    quota, limits = validate_profile_spec(
        profile.quota_hard_json or {},
        profile.limit_defaults_json or {},
    )
    storage_policy = validate_storage_policy(getattr(profile, 'storage_policy_json', {}) or {})
    return quota, limits, storage_policy, True


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
    storage_policy = _resource_profile_storage_values(profile_class, source)
    profile = TenantResourceProfile()
    profile.name = name
    profile.profile_class = profile_class
    profile.version = version
    profile.base_preset_class = base_preset_class
    profile.base_preset_version = base_preset_version
    profile.description = _text(source, 'profile_description') or None
    profile.quota_hard_json = quota
    profile.limit_defaults_json = limits
    profile.storage_policy_json = storage_policy
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

    is_builtin = profile.profile_class in RESOURCE_PROFILE_PRESETS
    if is_builtin:
        # Built-in profile identity and numeric sizing remain canonical. Operators
        # may revise the ownership mask and advanced-control intent as a new
        # contract version under the same logical profile.
        name = profile.name
        quota, limits = _preset_controlled_values(RESOURCE_PROFILE_PRESETS[profile.profile_class], source)
        storage_policy = _preset_storage_policy_values(RESOURCE_PROFILE_PRESETS[profile.profile_class], source)
    else:
        name = _text(source, 'profile_name')
        if not name or len(name) > 120:
            raise ValueError('Resource Profile name is required and must be at most 120 characters.')
        duplicate = TenantResourceProfile.query.filter(
            func.lower(TenantResourceProfile.name) == name.lower(),
            TenantResourceProfile.id != profile.id,
        ).first()
        if duplicate is not None:
            raise ValueError('A Resource Profile with this name already exists.')
        quota, limits = _profile_values(source)
        storage_policy = _storage_policy_values(source)

    enabled_value = _text(source, 'profile_enabled').lower() or ('enabled' if profile.enabled else 'disabled')
    if enabled_value not in {'enabled', 'disabled'}:
        raise ValueError('Select whether the Resource Profile is Enabled or Disabled.')

    advanced_controls = _advanced_profile_controls(source)
    contract_changed = (
        quota != (profile.quota_hard_json or {})
        or limits != (profile.limit_defaults_json or {})
        or storage_policy != (getattr(profile, 'storage_policy_json', {}) or {})
        or advanced_controls != (profile.advanced_controls_json or {})
    )

    profile.name = name
    if 'profile_description' in source:
        profile.description = _text(source, 'profile_description') or None
    profile.quota_hard_json = quota
    profile.limit_defaults_json = limits
    profile.storage_policy_json = storage_policy
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


def rollout_resource_profile_to_tenant_committed(
    *,
    profile_id: int,
    tenant_id: str,
) -> dict[str, Any]:
    profile = db.session.get(TenantResourceProfile, profile_id)
    if profile is None or not profile.enabled:
        raise ValueError('Selected Resource Profile is unavailable.')

    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant is not Ready; Resource Profile rollout is unavailable.')
    if tenant.provider_key != 'native_kubernetes':
        raise ValueError(
            'Bulk Namespace profile rollout currently uses Native Kubernetes authority only. '
            'Capsule allocations must use their admitted Capsule governance workflow.'
        )

    records = (
        TenantNamespace.query.join(
            TenantEnvironment,
            TenantEnvironment.id == TenantNamespace.tenant_environment_id,
        )
        .filter(
            TenantNamespace.resource_profile_id == profile.id,
            TenantEnvironment.tenant_id == tenant.id,
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .order_by(TenantNamespace.namespace.asc(), TenantNamespace.id.asc())
        .all()
    )
    if not records:
        raise ValueError('No active Namespace attachment uses this Resource Profile for the selected Tenant.')

    desired_quota, desired_limits, desired_storage, _ = _namespace_allocation_values(profile)

    summary: dict[str, Any] = {
        'profile_id': profile.public_id,
        'profile_name': profile.name,
        'profile_version': int(profile.version or 1),
        'tenant_id': tenant.id,
        'tenant_name': tenant.name,
        'total': len(records),
        'updated': 0,
        'already_current': 0,
        'failed': [],
    }

    for record in records:
        if (
            int(record.resource_profile_version or 0) == int(profile.version or 1)
            and dict(record.allocation_quota_json or {}) == desired_quota
            and dict(record.allocation_limit_defaults_json or {}) == desired_limits
            and dict(record.allocation_storage_policy_json or {}) == desired_storage
        ):
            summary['already_current'] += 1
            continue

        try:
            change_native_namespace_allocation_committed(
                {
                    'tenant_namespace_id': str(record.id),
                    'resource_profile_id': str(profile.id),
                }
            )
        except (ApiException, ValueError, TenantStateConflictError) as exc:
            summary['failed'].append({'namespace': record.namespace, 'reason': str(exc)})
            continue

        summary['updated'] += 1

    return summary


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

    _validate_resource_profile_base_controls(profile, tenant)
    attachment_controls = _validate_resource_profile_attachment_controls(profile, tenant)
    quota, limits, storage_policy, customized = _namespace_allocation_values(profile)
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
        storage_policy=storage_policy,
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
            'This Namespace allocation is not in KAORI Managed control; select a managed Native allocation.'
        )

    _validate_resource_profile_base_controls(profile, record.environment.tenant)
    attachment_controls = _validate_resource_profile_attachment_controls(profile, record.environment.tenant)
    quota, limits, storage_policy, customized = _namespace_allocation_values(profile)
    capacity_decision = enforce_existing_namespace_allocation_preflight(
        record=record,
        profile=profile,
        quota_hard=quota,
    )

    profile_version = int(profile.version or 1)

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
                storage_policy=storage_policy,
                operation='allocation_change',
            )
        else:
            record.resource_profile = profile
            record.resource_profile_id = profile.id
            record.resource_profile_version = profile_version
            record.allocation_quota_json = quota
            record.allocation_limit_defaults_json = limits
            record.allocation_storage_policy_json = storage_policy
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


def _materialize_adopted_baseline_profile(record: TenantNamespace) -> TenantResourceProfile:
    evidence = record.provisioning_evidence_json or {}
    allocation = evidence.get('allocation')
    allocation = dict(allocation) if isinstance(allocation, Mapping) else {}
    lineage = allocation.get('profile_lineage')
    lineage = dict(lineage) if isinstance(lineage, Mapping) else {}

    profile = TenantResourceProfile()
    profile.public_id = str(uuid.uuid4())
    profile.name = f'Adopted {record.namespace} Baseline · {record.id}'
    profile.profile_class = TenantResourceProfileClass.CUSTOM.value
    profile.version = 1
    profile.base_preset_class = (
        str(lineage.get('profile_class') or '').strip() if lineage.get('kind') == 'kaori_preset' else None
    )
    profile.base_preset_version = (
        int(lineage.get('profile_version'))
        if profile.base_preset_class and lineage.get('profile_version') is not None
        else None
    )
    profile.description = (
        'Explicit governance-cutover profile materialized from the adopted provider baseline. '
        'No provider value change is requested by this baseline.'
    )
    profile.quota_hard_json = dict(record.allocation_quota_json or {})
    profile.limit_defaults_json = dict(record.allocation_limit_defaults_json or {})
    profile.storage_policy_json = dict(record.allocation_storage_policy_json or {})
    profile.advanced_controls_json = {}
    profile.enabled = True
    db.session.add(profile)
    db.session.flush()
    return profile


def cutover_adopted_namespace_allocation(source: Mapping[str, Any]) -> TenantNamespace:
    try:
        namespace_id = int(_text(source, 'tenant_namespace_id'))
    except ValueError as exc:
        raise ValueError('Select an adopted Tenant namespace.') from exc

    record = db.session.get(TenantNamespace, namespace_id)
    if record is None:
        raise ValueError('Select an adopted Tenant namespace.')
    if record.ownership_status != TenantOwnershipStatus.ADOPTED.value:
        raise ValueError('Allocation governance cutover requires an Adopted Tenant namespace.')

    tenant = record.environment.tenant
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant is not Ready; allocation governance cutover is frozen during teardown.')

    cutover = build_allocation_cutover_state(record)
    if not cutover['supported']:
        raise ValueError(str(cutover['reason']))

    profile_selector = _text(source, 'resource_profile_id')
    if profile_selector == 'adopted_baseline':
        profile = _materialize_adopted_baseline_profile(record)
    else:
        try:
            profile_id = int(profile_selector)
        except ValueError as exc:
            raise ValueError('Select an enabled Resource Profile.') from exc
        profile = db.session.get(TenantResourceProfile, profile_id)
        if profile is None or not profile.enabled:
            raise ValueError('Select an enabled Resource Profile.')

    _validate_resource_profile_base_controls(profile, tenant)
    attachment_controls = _validate_resource_profile_attachment_controls(profile, tenant)
    quota, limits, storage_policy, customized = _namespace_allocation_values(profile)
    capacity_decision = enforce_existing_namespace_allocation_preflight(
        record=record,
        profile=profile,
        quota_hard=quota,
    )
    reconcile_adopted_native_allocation(
        record,
        profile=profile,
        resource_profile_version=profile.version,
        allocation_customized=customized,
        capacity_decision_id=capacity_decision.id,
        quota_hard=quota,
        limit_defaults=limits,
        storage_policy=storage_policy,
        operation='allocation_governance_cutover',
    )
    evidence = dict(record.provisioning_evidence_json or {})
    evidence['advanced_profile_controls'] = {
        'source_profile_id': profile.public_id,
        'source_profile_version': int(profile.version or 1),
        'provider_key': record.environment.tenant.provider_key,
        'controls': attachment_controls,
    }
    if profile_selector == 'adopted_baseline':
        evidence['baseline_profile_materialization'] = {
            'profile_id': profile.public_id,
            'profile_version': profile.version,
            'source': 'adopted_provider_baseline',
            'provider_value_change_requested': False,
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


