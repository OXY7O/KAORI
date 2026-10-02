from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.domain_exposure import normalize_domain_pattern
from app.kubernetes.tenant.native_provider import NativeKubernetesTenantProvider
from app.kubernetes.tenant.service_contracts import (
    _CONTROL_TRUE_VALUES,
    RESOURCE_PROFILE_ADVANCED_CONTROLS,
    _text,
)
from app.models import Cluster
from app.models.tenant import Tenant, TenantResourceProfile
from app.models.tenant_managed_resource import TenantManagedResourceMode


def _control_contract_present(source: Mapping[str, Any]) -> bool:
    return _text(source, 'control_contract_present').lower() in _CONTROL_TRUE_VALUES


def _control_enabled(source: Mapping[str, Any], field: str) -> bool:
    if not _control_contract_present(source):
        return True
    return _text(source, f'control_{field}').lower() in _CONTROL_TRUE_VALUES


def _advanced_control_contract_present(source: Mapping[str, Any]) -> bool:
    return _text(source, 'advanced_control_contract_present').lower() in _CONTROL_TRUE_VALUES


def _advanced_enabled(source: Mapping[str, Any], key: str) -> bool:
    return _text(source, f'advanced_control_{key}').lower() in _CONTROL_TRUE_VALUES


def _advanced_choice(
    source: Mapping[str, Any],
    key: str,
    field: str,
    *,
    allowed: set[str],
    default: str,
) -> str:
    value = _text(source, f'advanced_control_{key}_{field}').lower() or default
    if value not in allowed:
        raise ValueError(
            f'Select a supported {field.replace("_", " ")} for {RESOURCE_PROFILE_ADVANCED_CONTROLS[key]["label"]}.'
        )
    return value


def _advanced_bool_choice(
    source: Mapping[str, Any],
    key: str,
    field: str,
    *,
    default: bool,
) -> bool:
    value = _text(source, f'advanced_control_{key}_{field}').lower()
    if not value:
        return default
    if value in {'allow', 'enabled', 'true', '1', 'yes', 'required'}:
        return True
    if value in {'deny', 'disabled', 'false', '0', 'no', 'preflight_only'}:
        return False
    raise ValueError(
        f'Select a supported {field.replace("_", " ")} value for {RESOURCE_PROFILE_ADVANCED_CONTROLS[key]["label"]}.'
    )


def _advanced_json(
    source: Mapping[str, Any],
    key: str,
    field: str,
    *,
    default: object,
    require_mapping: bool = False,
    require_non_empty: bool = False,
) -> object:
    raw = _text(source, f'advanced_control_{key}_{field}')
    if not raw:
        value = default
    else:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f'{RESOURCE_PROFILE_ADVANCED_CONTROLS[key]["label"]} {field.replace("_", " ")} must be valid JSON.'
            ) from exc
    if require_mapping and not isinstance(value, dict):
        raise ValueError(
            f'{RESOURCE_PROFILE_ADVANCED_CONTROLS[key]["label"]} {field.replace("_", " ")} must be a JSON object.'
        )
    if require_non_empty and not value:
        raise ValueError(
            f'{RESOURCE_PROFILE_ADVANCED_CONTROLS[key]["label"]} {field.replace("_", " ")} cannot be empty.'
        )
    return value


def _advanced_csv(source: Mapping[str, Any], key: str, field: str) -> list[str]:
    raw = _text(source, f'advanced_control_{key}_{field}')
    return list(dict.fromkeys(item.strip() for item in raw.split(',') if item.strip()))


def _base_advanced_profile_controls(source: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    if _advanced_enabled(source, 'ingress'):
        controls['ingress'] = {
            'enabled': True,
            'enforcement_required': _advanced_bool_choice(
                source,
                'ingress',
                'enforcement_mode',
                default=True,
            ),
        }

    if _advanced_enabled(source, 'service_exposure'):
        profile_key = _advanced_choice(
            source,
            'service_exposure',
            'profile_key',
            allowed={'ingress_only', 'custom'},
            default='ingress_only',
        )
        if profile_key == 'ingress_only':
            exposure = {
                'allow_cluster_ip': True,
                'allow_ingress': True,
                'allow_node_port': False,
                'allow_load_balancer': False,
                'allow_external_name': False,
            }
        else:
            exposure = {
                field: _advanced_bool_choice(
                    source,
                    'service_exposure',
                    field,
                    default=default,
                )
                for field, default in {
                    'allow_cluster_ip': True,
                    'allow_ingress': True,
                    'allow_node_port': False,
                    'allow_load_balancer': False,
                    'allow_external_name': False,
                }.items()
            }
        controls['service_exposure'] = {'enabled': True, 'profile_key': profile_key, **exposure}

    if _advanced_enabled(source, 'hostname_reservation'):
        match_mode = _advanced_choice(
            source,
            'hostname_reservation',
            'match_mode',
            allowed={'exact', 'wildcard', 'regex'},
            default='exact',
        )
        hostname_pattern = _text(source, 'advanced_control_hostname_reservation_hostname_pattern')
        if not hostname_pattern:
            raise ValueError('Hostname Reservation requires a hostname pattern.')
        controls['hostname_reservation'] = {
            'enabled': True,
            'match_mode': match_mode,
            'hostname_pattern': normalize_domain_pattern(hostname_pattern, match_mode),
        }
    return controls


def _managed_advanced_profile_controls(source: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    if _advanced_enabled(source, 'managed_tls'):
        mode = _advanced_choice(
            source,
            'managed_tls',
            'mode',
            allowed={
                TenantManagedResourceMode.PLATFORM_TLS.value,
                TenantManagedResourceMode.NAMESPACE_TLS_COMPAT.value,
            },
            default=TenantManagedResourceMode.PLATFORM_TLS.value,
        )
        resource_name = _text(source, 'advanced_control_managed_tls_resource_name') or 'tenant-tls'
        source_reference = _text(source, 'advanced_control_managed_tls_source_reference') or None
        if mode == TenantManagedResourceMode.NAMESPACE_TLS_COMPAT.value and not source_reference:
            raise ValueError('Managed TLS namespace compatibility mode requires a non-secret source reference.')
        controls['managed_tls'] = {
            'enabled': True,
            'mode': mode,
            'resource_name': resource_name,
            'source_reference': source_reference,
        }

    if _advanced_enabled(source, 'managed_registry'):
        mode = _advanced_choice(
            source,
            'managed_registry',
            'mode',
            allowed={
                TenantManagedResourceMode.IMAGE_PULL_SECRET.value,
                TenantManagedResourceMode.EXTERNAL_CREDENTIAL_PROVIDER.value,
            },
            default=TenantManagedResourceMode.IMAGE_PULL_SECRET.value,
        )
        resource_name = _text(source, 'advanced_control_managed_registry_resource_name') or 'registry-credentials'
        source_reference = _text(source, 'advanced_control_managed_registry_source_reference') or None
        if mode == TenantManagedResourceMode.IMAGE_PULL_SECRET.value and not source_reference:
            raise ValueError('Managed Registry image-pull Secret mode requires a non-secret source reference.')
        controls['managed_registry'] = {
            'enabled': True,
            'mode': mode,
            'resource_name': resource_name,
            'source_reference': source_reference,
        }
    return controls


def _capsule_advanced_profile_controls(source: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    if _advanced_enabled(source, 'capsule_namespace_controls'):
        controls['capsule_namespace_controls'] = {
            'enabled': True,
            'force_tenant_prefix': _advanced_bool_choice(
                source,
                'capsule_namespace_controls',
                'force_tenant_prefix',
                default=False,
            ),
            'namespace_options': _advanced_json(
                source,
                'capsule_namespace_controls',
                'namespace_options_json',
                default={},
                require_mapping=True,
            ),
        }

    if _advanced_enabled(source, 'capsule_resource_rules'):
        controls['capsule_resource_rules'] = {
            'enabled': True,
            'container_registries': _advanced_csv(source, 'capsule_resource_rules', 'container_registries'),
            'priority_classes': _advanced_csv(source, 'capsule_resource_rules', 'priority_classes'),
            'storage_classes': _advanced_csv(source, 'capsule_resource_rules', 'storage_classes'),
            'rules': _advanced_json(source, 'capsule_resource_rules', 'rules_json', default=[]),
        }

    if _advanced_enabled(source, 'capsule_resource_pools'):
        kind = _advanced_choice(
            source,
            'capsule_resource_pools',
            'resource_kind',
            allowed={'resource_pool', 'resource_pool_claim'},
            default='resource_pool',
        )
        resource_name = _text(source, 'advanced_control_capsule_resource_pools_resource_name')
        if not resource_name:
            raise ValueError('Capsule Resource Pools requires a resource name.')
        controls['capsule_resource_pools'] = {
            'enabled': True,
            'resource_kind': kind,
            'resource_name': resource_name,
            'spec': _advanced_json(
                source,
                'capsule_resource_pools',
                'spec_json',
                default={},
                require_mapping=True,
                require_non_empty=True,
            ),
        }

    if _advanced_enabled(source, 'capsule_replication'):
        kind = _advanced_choice(
            source,
            'capsule_replication',
            'resource_kind',
            allowed={'tenant_resource', 'global_tenant_resource'},
            default='tenant_resource',
        )
        resource_name = _text(source, 'advanced_control_capsule_replication_resource_name')
        if not resource_name:
            raise ValueError('Capsule Replication requires a resource name.')
        controls['capsule_replication'] = {
            'enabled': True,
            'resource_kind': kind,
            'resource_name': resource_name,
            'spec': _advanced_json(
                source,
                'capsule_replication',
                'spec_json',
                default={},
                require_mapping=True,
                require_non_empty=True,
            ),
        }

    if _advanced_enabled(source, 'capsule_tenant_cordon'):
        cordoned = _advanced_bool_choice(source, 'capsule_tenant_cordon', 'cordoned', default=True)
        prevent_deletion = _advanced_bool_choice(
            source,
            'capsule_tenant_cordon',
            'prevent_deletion',
            default=False,
        )
        if not cordoned and not prevent_deletion:
            raise ValueError('Capsule Tenant Cordon must enable cordon, deletion protection, or both.')
        controls['capsule_tenant_cordon'] = {
            'enabled': True,
            'cordoned': cordoned,
            'prevent_deletion': prevent_deletion,
        }
    return controls


def _advanced_profile_controls(source: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if not _advanced_control_contract_present(source):
        return {}
    return {
        **_base_advanced_profile_controls(source),
        **_managed_advanced_profile_controls(source),
        **_capsule_advanced_profile_controls(source),
    }


def _advanced_control_request(value: Any) -> tuple[bool, dict[str, Any]]:
    if isinstance(value, Mapping):
        requested = bool(value.get('enabled', True))
        config = {str(key): item for key, item in value.items() if key != 'enabled'}
        return requested, config
    return bool(value), {}


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
        requested, configuration = _advanced_control_request(requested_controls.get(key))
        provider_requirements = dict(contract.get('providers') or {}).get(provider_key)
        if provider_requirements is not None:
            provider_requirements = tuple(provider_requirements)
            if key == 'ingress' and not bool(configuration.get('enforcement_required', True)):
                provider_requirements = tuple(
                    capability for capability in provider_requirements if capability != 'admission_enforcement'
                )
            if (
                key == 'managed_registry'
                and provider_key == 'native_kubernetes'
                and configuration.get('mode') == TenantManagedResourceMode.EXTERNAL_CREDENTIAL_PROVIDER.value
            ):
                provider_requirements = (*provider_requirements, 'external_registry_provider')

        if not requested:
            state = 'disabled'
            reason = 'Not enabled in this Resource Profile.'
        elif provider_requirements is None:
            state = 'unsupported'
            reason = f'{contract["label"]} is not supported by the {provider_key.replace("_", " ")} placement.'
        else:
            unavailable = [
                capability for capability in provider_requirements if statuses.get(capability) != 'available'
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
            'configuration': configuration,
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
        provider = NativeKubernetesTenantProvider(connection=connection)
        return {item.key: item.status.value for item in provider.capabilities(cluster_id=str(tenant.cluster_id))}

    evidence = tenant.provider_evidence_json or {}
    capsule = evidence.get('capsule') if isinstance(evidence, Mapping) else None
    capsule = capsule if isinstance(capsule, Mapping) else evidence
    capabilities = capsule.get('capabilities') if isinstance(capsule, Mapping) else {}
    return {str(key): str(value) for key, value in dict(capabilities or {}).items()}


def resource_profile_base_control_state(
    profile: TenantResourceProfile,
    *,
    provider_key: str,
) -> dict[str, dict[str, Any]]:
    configured = {
        'resource_quota': bool(profile.quota_hard_json or {}),
        'container_defaults': bool(profile.limit_defaults_json or {}),
        'pvc_storage_policy': bool(getattr(profile, 'storage_policy_json', {}) or {}),
    }
    supported = {
        'native_kubernetes': {
            'resource_quota': True,
            'container_defaults': True,
            'pvc_storage_policy': True,
        },
        'capsule': {
            'resource_quota': True,
            'container_defaults': False,
            'pvc_storage_policy': False,
        },
    }.get(provider_key, {})
    labels = {
        'resource_quota': 'ResourceQuota',
        'container_defaults': 'Container Defaults',
        'pvc_storage_policy': 'PVC Storage Guardrails',
    }
    return {
        key: {
            'key': key,
            'label': labels[key],
            'configured': value,
            'state': ('managed' if value and supported.get(key) is True else 'unsupported' if value else 'off'),
            'reason': (
                'Configured profile control is supported by the authoritative provider path.'
                if value and supported.get(key) is True
                else (
                    f'{labels[key]} is configured but the {provider_key.replace("_", " ")} attachment path '
                    'has no admitted write/read-back authority for this control.'
                )
                if value
                else 'Not configured in this Resource Profile.'
            ),
        }
        for key, value in configured.items()
    }


def _validate_resource_profile_base_controls(
    profile: TenantResourceProfile,
    tenant: Tenant,
) -> dict[str, dict[str, Any]]:
    state = resource_profile_base_control_state(profile, provider_key=tenant.provider_key)
    unsupported = [item['label'] for item in state.values() if item['configured'] and item['state'] == 'unsupported']
    if unsupported:
        raise ValueError(
            'Resource Profile contains controls without admitted '
            f'{tenant.provider_key.replace("_", " ")} authority: '
            + ', '.join(unsupported)
            + '. Disable those Managed dimensions or use a compatible provider placement.'
        )
    return state


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
        item['label'] for item in evaluation.values() if item['requested'] and item['state'] == 'unsupported'
    ]
    if unsupported:
        raise ValueError(
            'Resource Profile advanced controls are unavailable on the selected provider placement: '
            + ', '.join(unsupported)
            + '.'
        )
    return evaluation
