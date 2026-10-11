"""Bounded, non-mutating provider allocation handoff evidence for Tenant Release.

Ownership markers establish correlation, not approval to delete or transfer a
provider resource. Kubernetes and Capsule remain authoritative.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS

_MAX_COMPONENTS = 100
_MAX_CAPSULE_SPEC_BYTES = 262_144
_MANAGER_KEY = 'app.kubernetes.io/managed-by'
_TENANT_ID_KEY = 'kaori.io/tenant-id'


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _string(value: Any) -> str:
    return str(value or '').strip()


def _marker_state(*, labels: Mapping[str, Any], tenant_id: str) -> str:
    manager = _string(labels.get(_MANAGER_KEY)).lower()
    claim = _string(labels.get(_TENANT_ID_KEY))
    if manager == 'kaori' and claim == tenant_id:
        return 'kaori_marker_correlated'
    if manager == 'kaori' or claim:
        return 'marker_conflict'
    return 'external_or_unattributed'


def _component(
    *, kind: str, name: str, uid: str, version: str,
    labels: Mapping[str, Any], tenant_id: str,
) -> dict[str, str]:
    if not name or not uid or not version:
        raise ValueError(f'{kind} handoff lacks complete provider identity.')
    marker = _marker_state(labels=labels, tenant_id=tenant_id)
    return {
        'kind': kind,
        'name': name,
        'uid': uid,
        'resource_version': version,
        'ownership': marker,
        'managed_by': _string(labels.get(_MANAGER_KEY)),
        'handoff': (
            'owner_review_required' if marker == 'marker_conflict'
            else 'external_acceptance_required' if marker == 'kaori_marker_correlated'
            else 'observe_only'
        ),
    }


def native_namespace_handoff_evidence(
    *, record: Any, namespace: Any, observation: Mapping[str, Any], tenant_id: str
) -> tuple[list[dict[str, str]], list[str]]:
    """Classify observed Namespace, ResourceQuota and LimitRange with no mutation."""
    meta = _field(namespace, 'metadata')
    labels = _field(meta, 'labels') or {}
    if not isinstance(labels, Mapping):
        raise ValueError('Namespace ownership metadata is malformed.')
    namespace_name = _string(_field(meta, 'name'))
    if namespace_name != _string(record.namespace):
        raise ValueError('Namespace identity changed before Release handoff.')
    components = [
        _component(
            kind='Namespace', name=namespace_name,
            uid=_string(_field(meta, 'uid')),
            version=_string(_field(meta, 'resource_version') or _field(meta, 'resourceVersion')),
            labels=labels, tenant_id=tenant_id,
        )
    ]
    sources = observation.get('source_resources')
    if not isinstance(sources, list) or len(sources) > _MAX_COMPONENTS - 1:
        raise ValueError('Namespace quota/limit ownership inventory is unbounded or incomplete.')
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError('Namespace quota/limit metadata is malformed.')
        kind = _string(source.get('kind'))
        if kind not in {'ResourceQuota', 'LimitRange'}:
            raise ValueError('Unsupported allocation source in Release handoff.')
        components.append(_component(
            kind=kind, name=_string(source.get('name')),
            uid=_string(source.get('uid')),
            version=_string(source.get('resource_version')),
            labels={
                _MANAGER_KEY: source.get('managed_by'),
                _TENANT_ID_KEY: source.get('tenant_id'),
            },
            tenant_id=tenant_id,
        ))
    blockers = []
    if observation.get('control_state') != 'observed':
        blockers.append(f'{namespace_name} provider allocation authority is ambiguous or unavailable.')
    if _string(observation.get('effective_hash')) != _string(record.effective_hash):
        blockers.append(f'{namespace_name} allocation hash changed since committed KAORI evidence.')
    if any(item['ownership'] == 'marker_conflict' for item in components):
        blockers.append(f'{namespace_name} has inconsistent provider ownership markers.')
    needs_handoff = (
        record.resource_profile_id is not None
        or _string((record.provisioning_evidence_json or {}).get('allocation_control_state')) == 'kaori_managed'
        or (record.provisioning_evidence_json or {}).get('provider_mutation_performed') is True
        or any(item['ownership'] == 'kaori_marker_correlated' for item in components)
    )
    if needs_handoff:
        blockers.append(
            f'{namespace_name} KAORI-linked allocation ownership requires independently approved '
            'external handoff and provider read-back.'
        )
    return components, blockers


def _capsule_spec_sha256(spec: Any) -> str:
    """Bound and fingerprint the *entire* live Capsule spec; never persist its contents.

    Spec is provider-owned; the hash only binds the preflight to exact observed
    quota, limit, owner, Namespace options and RBAC contract for later consent.
    """
    if not isinstance(spec, Mapping):
        raise ValueError('Capsule Tenant handoff requires a complete provider spec.')
    for name, expected in (
        ('resourceQuotas', Mapping),
        ('limitRanges', Mapping),
        ('namespaceOptions', Mapping),
        ('permissions', Mapping),
        ('owners', list),
        ('additionalRoleBindings', list),
        ('rules', list),
    ):
        if name in spec and not isinstance(spec[name], expected):
            raise ValueError(f'Capsule Tenant {name} handoff schema is unsupported.')
    try:
        canonical = json.dumps(
            spec, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
            allow_nan=False,
        ).encode('utf-8')
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Capsule Tenant handoff spec is not canonical JSON.') from exc
    if len(canonical) > _MAX_CAPSULE_SPEC_BYTES:
        raise ValueError('Capsule Tenant handoff spec exceeds bounded evidence size.')
    return hashlib.sha256(canonical).hexdigest()


def capsule_tenant_handoff_evidence(
    *, tenant: Any, tenant_item: Mapping[str, Any]
) -> tuple[list[dict[str, str]], list[str]]:
    """Observe and fingerprint Capsule authority; never infer Release authorization."""
    metadata = tenant_item.get('metadata') or {}
    spec = tenant_item.get('spec')
    if not isinstance(metadata, Mapping):
        raise ValueError('Capsule Tenant handoff schema is incomplete.')
    spec_sha256 = _capsule_spec_sha256(spec)
    component = _component(
        kind='CapsuleTenant', name=_string(metadata.get('name')),
        uid=_string(metadata.get('uid')),
        version=_string(metadata.get('resourceVersion')),
        labels={_MANAGER_KEY: (metadata.get('labels') or {}).get(_MANAGER_KEY)},
        tenant_id=_string(tenant.id),
    )
    component['authority'] = 'capsule'
    component['resource_quotas_present'] = str('resourceQuotas' in spec).lower()
    component['capsule_spec_sha256'] = spec_sha256
    existing = tenant.provider_evidence_json or {}
    blockers = []
    if existing.get('provider_mutation_performed') is True:
        component['handoff'] = 'external_acceptance_required'
        blockers.append('Capsule allocation was modified by KAORI; explicit provider authority handoff is required.')
    elif existing.get('provider_mutation_performed') is not False:
        blockers.append('Capsule allocation mutation history is unknown; provider handoff is not admissible.')
    if component['ownership'] == 'marker_conflict':
        blockers.append('Capsule Tenant ownership metadata is conflicting.')
    return [component], blockers


def capsule_namespace_handoff_evidence(
    *, record: Any, namespace: Any, tenant_name: str,
    status_namespace_names: set[str], tenant_id: str,
) -> tuple[dict[str, str], list[str]]:
    """Verify a Namespace still belongs to the authoritative Capsule Tenant."""
    meta = _field(namespace, 'metadata')
    labels = _field(meta, 'labels') or {}
    if not isinstance(labels, Mapping):
        raise ValueError('Capsule Namespace ownership labels are malformed.')
    name = _string(_field(meta, 'name'))
    uid = _string(_field(meta, 'uid'))
    if name != _string(record.namespace) or uid != _string(record.provider_reference):
        raise ValueError('Capsule Namespace name/UID differs from the committed adoption record.')
    claims = {
        _string(labels.get(key))
        for key in _CAPSULE_TENANT_LABEL_KEYS
        if _string(labels.get(key))
    }
    blockers: list[str] = []
    if (claims and claims != {tenant_name}) or (not claims and name not in status_namespace_names):
        blockers.append(f'Capsule Namespace/{name} has no verifiable Tenant ownership correlation.')
    component = _component(
        kind='Namespace', name=name, uid=uid,
        version=_string(_field(meta, 'resource_version') or _field(meta, 'resourceVersion')),
        labels=labels, tenant_id=tenant_id,
    )
    component['authority'] = 'capsule'
    if component['ownership'] == 'marker_conflict':
        blockers.append(f'Capsule Namespace/{name} has inconsistent KAORI ownership markers.')
    return component, blockers


def handoff_fingerprint(components: list[dict[str, str]]) -> str:
    """Stable equality proof for the latest committed provider identity snapshot."""
    canonical = sorted(
        components,
        key=lambda item: (
            item.get('namespace', ''), item.get('kind', ''),
            item.get('name', ''), item.get('uid', ''),
        ),
    )
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
