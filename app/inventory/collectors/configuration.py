from __future__ import annotations

import base64
from typing import cast

from kubernetes.client import CoreV1Api, V1ConfigMapList, V1ResourceQuotaList, V1SecretList
from kubernetes.client.exceptions import ApiException


def get_configuration_inventory(
    api: CoreV1Api,
    *,
    include_configmaps: bool = True,
    include_secrets: bool = True,
) -> list[dict]:
    items: list[dict] = []

    try:
        if not include_configmaps:
            raise PermissionError
        config_maps = cast(
            V1ConfigMapList,
            api.list_config_map_for_all_namespaces(),
        )
        config_map_items = config_maps.items or []
    except PermissionError:
        config_map_items = []
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            config_map_items = []
        else:
            raise

    for config_map in config_map_items:
        metadata = config_map.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        data = config_map.data or {}
        binary_data = config_map.binary_data or {}
        key_names = sorted({*data.keys(), *binary_data.keys()})
        payload_size = sum(len(value.encode('utf-8')) for value in data.values())

        for value in binary_data.values():
            try:
                payload_size += len(base64.b64decode(value))
            except (ValueError, TypeError):
                payload_size += len(str(value).encode('utf-8'))

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'object_type': 'ConfigMap',
                'secret_type': None,
                'key_names': key_names,
                'key_count': len(key_names),
                'immutable': bool(config_map.immutable),
                'payload_size_bytes': payload_size,
                'created_at': metadata.creation_timestamp,
            }
        )

    try:
        if not include_secrets:
            raise PermissionError
        secrets = cast(
            V1SecretList,
            api.list_secret_for_all_namespaces(),
        )
        secret_items = secrets.items or []
    except PermissionError:
        secret_items = []
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            secret_items = []
        else:
            raise

    for secret in secret_items:
        metadata = secret.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        data = secret.data or {}
        string_data = secret.string_data or {}
        key_names = sorted({*data.keys(), *string_data.keys()})
        payload_size = 0

        for value in data.values():
            try:
                payload_size += len(base64.b64decode(value))
            except (ValueError, TypeError):
                payload_size += len(str(value).encode('utf-8'))

        payload_size += sum(len(value.encode('utf-8')) for value in string_data.values())

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'object_type': 'Secret',
                'secret_type': secret.type or 'Opaque',
                'key_names': key_names,
                'key_count': len(key_names),
                'immutable': bool(secret.immutable),
                'payload_size_bytes': payload_size,
                'created_at': metadata.creation_timestamp,
            }
        )

    return items


def get_resource_quotas(
    api: CoreV1Api,
) -> list[dict]:
    result = cast(
        V1ResourceQuotaList,
        api.list_resource_quota_for_all_namespaces(),
    )

    items: list[dict] = []

    for quota in result.items or []:
        metadata = quota.metadata
        status = quota.status

        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        hard = {str(key): str(value) for key, value in ((status.hard or {}) if status else {}).items()}
        used = {str(key): str(value) for key, value in ((status.used or {}) if status else {}).items()}

        items.append(
            {
                'namespace': metadata.namespace,
                'name': metadata.name,
                'hard': hard,
                'used': used,
                'created_at': metadata.creation_timestamp,
            }
        )

    return items
