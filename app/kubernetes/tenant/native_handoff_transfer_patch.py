"""Pure Native Kubernetes successor-marker patch contract for #1048.

This only constructs a conditional JSON Patch. It does NOT send it, approve a
successor, grant access, or mark any KAORI Tenant Released. The live executor
remains blocked by accepted #1047 identity/consent authority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.native_handoff_dry_run import (
    _label_path,
    build_native_handoff_patch,
)

# Kubernetes metadata label value, 63 characters maximum.
_SUCCESSOR_LABEL = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,61}[A-Za-z0-9])?\Z')


def build_native_successor_handoff_patch(
    component: Mapping[str, str],
    resource: Any,
    *,
    tenant_id: str,
    verified_successor_owner: str,
) -> list[dict[str, str]]:
    """Compose UID/RV compare-and-swap and narrowly scoped successor adoption.

    A separately admitted executor must *prove* the supplied owner with
    provider-backed consent, recheck admission, issue the patch and read back
    resource specs and foreign metadata. This helper does none of those steps.
    """
    owner = verified_successor_owner
    if (
        not isinstance(owner, str)
        or not _SUCCESSOR_LABEL.fullmatch(owner)
        or owner.lower() == 'kaori'
        or owner.lower().startswith('system')
    ):
        raise ValueError('A valid, non-KAORI Kubernetes successor label is required.')
    # Reuse the exact current proof of original KAORI ownership, UID, RV and
    # tenant ID. Never broaden the patch to quotas, RBAC or lifecycle fields.
    operations = build_native_handoff_patch(component, resource, tenant_id=tenant_id)
    operations.append({
        'op': 'add',
        'path': _label_path('app.kubernetes.io/managed-by'),
        'value': owner,
    })
    return operations
