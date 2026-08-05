from __future__ import annotations

from typing import Any, Literal, cast, overload

from kubernetes.client import CoreV1Api, V1ConfigMapList, V1ResourceQuotaList, V1SecretList
from kubernetes.client.exceptions import ApiException


COLLECTED = 'Collected'
PERMISSION_UNAVAILABLE = 'Permission Unavailable'
API_UNAVAILABLE = 'API Unavailable'
ADAPTER_NOT_SELECTED = 'Adapter Not Selected'


def _collection_error_state(exc: ApiException) -> str:
    return PERMISSION_UNAVAILABLE if getattr(exc, 'status', None) == 403 else API_UNAVAILABLE


def get_configuration_inventory(
    api: CoreV1Api,
    *,
    include_configmaps: bool = True,
    include_secrets: bool = True,
    with_evidence: bool = False,
) -> list[dict] | tuple[list[dict], dict[str, str]]:
    """Collect key-index metadata without inspecting or sizing object values.

    Kubernetes list responses necessarily arrive in the collector process, but KAORI only
    indexes key names and object metadata. Value content is not decoded, logged, persisted,
    or displayed.
    """
    items: list[dict] = []
    evidence: dict[str, str] = {
        'inventory.configmaps': ADAPTER_NOT_SELECTED if not include_configmaps else COLLECTED,
        'inventory.secrets': ADAPTER_NOT_SELECTED if not include_secrets else COLLECTED,
    }

    config_map_items = []
    if include_configmaps:
        try:
            config_maps = cast(V1ConfigMapList, api.list_config_map_for_all_namespaces())
            config_map_items = config_maps.items or []
        except ApiException as exc:
            if getattr(exc, 'status', None) in {403, 404}:
                evidence['inventory.configmaps'] = _collection_error_state(exc)
            else:
                raise

    for config_map in config_map_items:
        metadata = config_map.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue
        key_names = sorted({*(config_map.data or {}).keys(), *(config_map.binary_data or {}).keys()})
        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'object_type': 'ConfigMap',
                'secret_type': None,
                'key_names': key_names,
                'key_count': len(key_names),
                'immutable': bool(config_map.immutable),
                'payload_size_bytes': 0,
                'created_at': metadata.creation_timestamp,
            }
        )

    secret_items = []
    if include_secrets:
        try:
            secrets = cast(V1SecretList, api.list_secret_for_all_namespaces())
            secret_items = secrets.items or []
        except ApiException as exc:
            if getattr(exc, 'status', None) in {403, 404}:
                evidence['inventory.secrets'] = _collection_error_state(exc)
            else:
                raise

    for secret in secret_items:
        metadata = secret.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue
        key_names = sorted({*(secret.data or {}).keys(), *(secret.string_data or {}).keys()})
        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'object_type': 'Secret',
                'secret_type': secret.type or 'Opaque',
                'key_names': key_names,
                'key_count': len(key_names),
                'immutable': bool(secret.immutable),
                'payload_size_bytes': 0,
                'created_at': metadata.creation_timestamp,
            }
        )

    return (items, evidence) if with_evidence else items


@overload
def get_resource_quotas(
    api: CoreV1Api,
    *,
    with_evidence: Literal[False] = False,
) -> list[dict]: ...


@overload
def get_resource_quotas(
    api: CoreV1Api,
    *,
    with_evidence: Literal[True],
) -> tuple[list[dict], str]: ...


def get_resource_quotas(
    api: CoreV1Api,
    *,
    with_evidence: bool = False,
) -> list[dict] | tuple[list[dict], str]:
    evidence = COLLECTED
    try:
        result = cast(V1ResourceQuotaList, api.list_resource_quota_for_all_namespaces())
        quota_items = result.items or []
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            quota_items = []
            evidence = _collection_error_state(exc)
        else:
            raise

    items: list[dict[str, Any]] = []
    for quota in quota_items:
        metadata = quota.metadata
        spec = getattr(quota, 'spec', None)
        status = getattr(quota, 'status', None)
        if metadata is None or not metadata.namespace or not metadata.name:
            continue
        configured_hard = (spec.hard or {}) if spec else {}
        observed_hard = (status.hard or {}) if status else {}
        hard = {
            str(key): str(value)
            for key, value in (configured_hard or observed_hard).items()
        }
        used = {
            str(key): str(value)
            for key, value in ((status.used or {}) if status else {}).items()
        }
        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'hard': hard,
                'used': used,
                'created_at': metadata.creation_timestamp,
            }
        )
    return (items, evidence) if with_evidence else items
