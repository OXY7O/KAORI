from __future__ import annotations

import base64
import re
from typing import Any

from app.kubernetes_operations.configmaps.contracts import ConfigMapEntries

_DNS_LABEL = re.compile(r'^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$')
_KEY_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
_MAX_CONFIGMAP_DATA_BYTES = 1024 * 1024
_ALLOWED_ENTRY_KINDS = {'text', 'binary'}
_ALLOWED_UPDATE_MODES = {'merge', 'replace'}


def _entries_payload_size(data: dict[str, str], binary_data: dict[str, str]) -> int:
    total = 0
    for key, value in data.items():
        total += len(key.encode('utf-8')) + len(value.encode('utf-8'))
    for key, value in binary_data.items():
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Binary key "{key}" must contain valid base64 data.') from exc
        total += len(key.encode('utf-8')) + len(decoded)
    return total


def _enforce_payload_limit(payload_size: int) -> None:
    if payload_size > _MAX_CONFIGMAP_DATA_BYTES:
        raise ValueError('The ConfigMap data exceeds the Kubernetes 1 MiB limit.')


def validate_name(value: str, label: str) -> str:
    normalized = (value or '').strip()
    labels = normalized.split('.') if normalized else []
    if (
        not normalized
        or len(normalized) > 253
        or any(not part or len(part) > 63 or not _DNS_LABEL.fullmatch(part) for part in labels)
    ):
        raise ValueError(f'{label} must be a valid Kubernetes DNS subdomain.')
    return normalized


def validate_namespace_name(value: str) -> str:
    normalized = (value or '').strip()
    if not normalized or len(normalized) > 63 or not _DNS_LABEL.fullmatch(normalized):
        raise ValueError('Namespace must be a valid Kubernetes DNS label.')
    return normalized


def _decode_binary_value(key: str, value: str) -> tuple[str, int]:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Binary key "{key}" must contain valid base64 data.') from exc
    return base64.b64encode(decoded).decode('ascii'), len(decoded)


def parse_entries(form: Any) -> ConfigMapEntries:
    keys = list(form.getlist('entry_key'))
    values = list(form.getlist('entry_value'))
    kinds = list(form.getlist('entry_kind'))
    row_count = max(len(keys), len(values), len(kinds))

    data: dict[str, str] = {}
    binary_data: dict[str, str] = {}
    payload_size = 0

    for index in range(row_count):
        raw_key = keys[index] if index < len(keys) else ''
        value = values[index] if index < len(values) else ''
        kind = (kinds[index] if index < len(kinds) else 'text').strip().lower()
        key = (raw_key or '').strip()

        if not key:
            if value:
                raise ValueError(f'ConfigMap entry row {index + 1} has a value but no key.')
            continue
        if len(key) > 253 or not _KEY_PATTERN.fullmatch(key):
            raise ValueError(f'ConfigMap key "{key}" contains unsupported characters.')
        if key in data or key in binary_data:
            raise ValueError(f'ConfigMap key "{key}" is duplicated.')
        if kind not in _ALLOWED_ENTRY_KINDS:
            raise ValueError(f'ConfigMap key "{key}" has an unsupported content type.')

        key_size = len(key.encode('utf-8'))
        if kind == 'binary':
            normalized_value, decoded_size = _decode_binary_value(key, value)
            binary_data[key] = normalized_value
            payload_size += key_size + decoded_size
        else:
            text_value = str(value)
            data[key] = text_value
            payload_size += key_size + len(text_value.encode('utf-8'))

    if not data and not binary_data:
        raise ValueError('Add at least one ConfigMap key before validating.')
    _enforce_payload_limit(payload_size)

    return ConfigMapEntries(
        data=data,
        binary_data=binary_data,
        payload_size_bytes=payload_size,
    )


def normalize_update_mode(value: str | None) -> str:
    mode = str(value or 'merge').strip().lower()
    if mode not in _ALLOWED_UPDATE_MODES:
        raise ValueError('Update mode must be Merge or Replace.')
    return mode


def merge_entries(existing: dict[str, Any], submitted: ConfigMapEntries, mode: str) -> ConfigMapEntries:
    normalized_mode = normalize_update_mode(mode)
    if normalized_mode == 'replace':
        return submitted

    merged_data = dict(existing['data'])
    merged_binary = dict(existing['binary_data'])
    for key, value in submitted.data.items():
        merged_binary.pop(key, None)
        merged_data[key] = value
    for key, value in submitted.binary_data.items():
        merged_data.pop(key, None)
        merged_binary[key] = value

    payload_size = _entries_payload_size(merged_data, merged_binary)
    _enforce_payload_limit(payload_size)
    return ConfigMapEntries(
        data=merged_data,
        binary_data=merged_binary,
        payload_size_bytes=payload_size,
    )


def diff_entries(existing: dict[str, Any], proposed: ConfigMapEntries) -> dict[str, list[str]]:
    old = {
        **{key: ('text', value) for key, value in existing['data'].items()},
        **{key: ('binary', value) for key, value in existing['binary_data'].items()},
    }
    new = {
        **{key: ('text', value) for key, value in proposed.data.items()},
        **{key: ('binary', value) for key, value in proposed.binary_data.items()},
    }
    return {
        'added': sorted(set(new) - set(old)),
        'changed': sorted(key for key in set(old) & set(new) if old[key] != new[key]),
        'removed': sorted(set(old) - set(new)),
        'unchanged': sorted(key for key in set(old) & set(new) if old[key] == new[key]),
    }
