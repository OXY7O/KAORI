"""Minimal Kubernetes ownerReference evidence for potential TLS controllers.

A Kubernetes ownerReference is an *object ownership claim*, not evidence that
a controller sourced certificate bytes from Vault or synchronized a Secret.
Only safe controller kind/group and immutable UID are retained; names,
annotations, provider paths and Secret data are not retained in this field.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

_MAX_OWNERS = 8
# Source-qualified controller types are deliberately narrow; others remain
# unsupported, not assumed to be unrelated to the Secret.
_SUPPORTED = {
    'ExternalSecret': 'external-secrets.io',
    'Certificate': 'cert-manager.io',
}


def _uid(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        result = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None
    return result if value.lower() == result else None


def normalize_tls_controller_owner(metadata: Any) -> list[dict[str, str]] | None:
    """Return candidate controller identity, [] when none, None when malformed.

    Any admitted Kubernetes object permits at most one ownerReference with
    controller=true. Other noncontroller and unsupported references are not
    used for Vault lineage. Presence is never proof of controller readback.
    """
    if metadata is None:
        return None
    raw = getattr(metadata, 'owner_references', None)
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > _MAX_OWNERS:
        return None
    owners: list[dict[str, str]] = []
    controller_refs = 0
    for item in raw:
        if getattr(item, 'controller', None) is not True:
            continue
        controller_refs += 1
        if controller_refs > 1:
            return None
        kind = getattr(item, 'kind', None)
        version = getattr(item, 'api_version', None)
        if kind not in _SUPPORTED:
            continue
        if not isinstance(version, str) or '/' not in version:
            return None
        group, api_version = version.rsplit('/', 1)
        if group != _SUPPORTED[kind] or api_version not in {'v1', 'v1beta1'}:
            return None
        parsed_uid = _uid(getattr(item, 'uid', None))
        if parsed_uid is None:
            return None
        owners.append({'kind': kind, 'api_group': group, 'uid': parsed_uid})
    return owners


def validate_committed_controller_owners(value: object) -> list[dict[str, str]] | None:
    """Reject tampered/legacy JSON rather than treating it as no controller.

    This is an *evidence readback* validator, not a general JSON parser.
    """
    if value is None or not isinstance(value, list) or len(value) > 1:
        return None
    output: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {'kind', 'api_group', 'uid'}:
            return None
        kind = item['kind']
        if kind not in _SUPPORTED or item['api_group'] != _SUPPORTED[kind]:
            return None
        uid = _uid(item['uid'])
        if uid is None or uid != item['uid']:
            return None
        output.append({'kind': kind, 'api_group': item['api_group'], 'uid': uid})
    return output
