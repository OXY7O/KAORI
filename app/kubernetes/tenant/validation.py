from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from kubernetes.utils.quantity import parse_quantity

SUPPORTED_QUOTA_KEYS = frozenset(
    {
        'requests.cpu',
        'limits.cpu',
        'requests.memory',
        'limits.memory',
        'pods',
        'persistentvolumeclaims',
        'requests.storage',
        'services',
        'configmaps',
        'secrets',
    }
)
COUNT_QUOTA_KEYS = frozenset({'pods', 'persistentvolumeclaims', 'services', 'configmaps', 'secrets'})
SUPPORTED_LIMIT_KEYS = frozenset({'cpu', 'memory'})
_NAMESPACE_RE = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')


def validate_namespace_name(namespace: str) -> str:
    value = namespace.strip()
    if not value or len(value) > 63 or _NAMESPACE_RE.fullmatch(value) is None:
        raise ValueError('namespace must be a valid DNS label with at most 63 characters')
    return value


def _positive_quantity(value: object, *, key: str) -> str:
    rendered = str(value).strip()
    if not rendered:
        raise ValueError(f'{key} requires a positive Kubernetes resource quantity')
    try:
        parsed = parse_quantity(rendered)
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ValueError(f'{key} has an invalid Kubernetes resource quantity') from exc
    if Decimal(parsed) <= 0:
        raise ValueError(f'{key} requires a positive Kubernetes resource quantity')
    return rendered


def validate_profile_spec(
    quota_hard: dict[str, object],
    limit_defaults: dict[str, dict[str, object]] | None = None,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    if not quota_hard:
        raise ValueError('resource profile must define at least one quota value')

    unsupported = sorted(set(quota_hard) - SUPPORTED_QUOTA_KEYS)
    if unsupported:
        raise ValueError(f'unsupported quota key(s): {", ".join(unsupported)}')

    normalized_quota: dict[str, str] = {}
    for key, raw in quota_hard.items():
        if key in COUNT_QUOTA_KEYS:
            rendered = str(raw).strip()
            if not rendered.isdigit() or int(rendered) <= 0:
                raise ValueError(f'{key} requires a positive integer')
            normalized_quota[key] = rendered
        else:
            normalized_quota[key] = _positive_quantity(raw, key=key)

    normalized_limits: dict[str, dict[str, str]] = {}
    for field, values in (limit_defaults or {}).items():
        if field not in {'default', 'default_request'}:
            raise ValueError(f'unsupported LimitRange field: {field}')
        unsupported_limits = sorted(set(values) - SUPPORTED_LIMIT_KEYS)
        if unsupported_limits:
            raise ValueError(f'unsupported LimitRange resource(s): {", ".join(unsupported_limits)}')
        normalized_limits[field] = {key: _positive_quantity(raw, key=f'{field}.{key}') for key, raw in values.items()}

    return normalized_quota, normalized_limits
