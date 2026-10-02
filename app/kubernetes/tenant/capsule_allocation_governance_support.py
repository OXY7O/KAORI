from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.kubernetes.tenant.allocation_cutover import _quantity_equal
from app.models.tenant import Tenant


def _canonical_hash(payload: object) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _tenant_evidence(tenant: Tenant) -> dict[str, Any]:
    return deepcopy(tenant.provider_evidence_json or {})


def _allocation_baseline(tenant: Tenant) -> dict[str, Any]:
    baseline = _tenant_evidence(tenant).get('allocation_baseline')
    return dict(baseline) if isinstance(baseline, Mapping) else {}


def _capsule_capability_state(tenant: Tenant, capability: str) -> str:
    capsule = _tenant_evidence(tenant).get('capsule')
    capabilities = capsule.get('capabilities') if isinstance(capsule, Mapping) else None
    return str(capabilities.get(capability) or '') if isinstance(capabilities, Mapping) else ''


def _source_reference(payload: Mapping[str, Any]) -> dict[str, str]:
    metadata = payload.get('metadata') if isinstance(payload, Mapping) else {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    return {
        'kind': 'GlobalResourceQuota',
        'name': str(metadata.get('name') or ''),
        'uid': str(metadata.get('uid') or ''),
        'resource_version': str(metadata.get('resourceVersion') or ''),
    }


def _quota_from_global_resource(payload: Mapping[str, Any]) -> dict[str, str]:
    spec = payload.get('spec') if isinstance(payload, Mapping) else {}
    spec = spec if isinstance(spec, Mapping) else {}
    quota = spec.get('quota')
    quota = quota if isinstance(quota, Mapping) else {}
    hard = quota.get('hard')
    return {str(key): str(value) for key, value in dict(hard or {}).items()} if isinstance(hard, Mapping) else {}


def _desired_shared_spec(current: Mapping[str, Any], quota_hard: Mapping[str, object]) -> dict[str, Any]:
    spec = current.get('spec') if isinstance(current, Mapping) else {}
    desired = deepcopy(dict(spec)) if isinstance(spec, Mapping) else {}
    quota = desired.get('quota')
    quota = deepcopy(dict(quota)) if isinstance(quota, Mapping) else {}
    quota['hard'] = {str(key): str(value) for key, value in quota_hard.items()}
    desired['quota'] = quota
    return desired


def _shared_authority_context(spec: Mapping[str, Any]) -> dict[str, Any]:
    context = deepcopy(dict(spec))
    quota = context.get('quota')
    if isinstance(quota, Mapping):
        quota_context = deepcopy(dict(quota))
        quota_context.pop('hard', None)
        if quota_context:
            context['quota'] = quota_context
        else:
            context.pop('quota', None)
    return context


def _quota_differences(
    desired: Mapping[str, object],
    observed: Mapping[str, object],
) -> list[dict[str, str]]:
    differences: list[dict[str, str]] = []
    for key in sorted(set(desired) | set(observed)):
        left = str(desired.get(key) or 'Unbounded')
        right = str(observed.get(key) or 'Unbounded')
        if not _quantity_equal(key, left, right):
            differences.append(
                {
                    'dimension': key,
                    'kaori_value': left,
                    'provider_value': right,
                }
            )
    return differences
