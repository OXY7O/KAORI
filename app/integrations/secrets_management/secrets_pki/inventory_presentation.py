"""Bounded, committed-state-only inventory readiness for Vault administrators."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.secrets_pki import SecretInventoryCollectionState
from app.models.vault import VaultInstance


def vault_inventory_readiness(instance: VaultInstance) -> dict[str, Any]:
    """Present scoped committed metadata only; never contact the Vault API."""
    configured = tuple(instance.kv2_mounts or ())
    if not configured:
        return {
            'state': 'not_configured',
            'approved_mount_count': 0,
            'committed_mount_count': 0,
            'observed_secret_count': None,
            'last_committed_at': None,
        }
    # At most eight explicitly configured scopes; retired scopes are excluded.
    states = (
        SecretInventoryCollectionState.query.filter(
            SecretInventoryCollectionState.integration_instance_id == instance.integration_instance_id,
            SecretInventoryCollectionState.provider_namespace == (instance.namespace or ''),
            SecretInventoryCollectionState.mount.in_(configured),
        )
        .limit(8)
        .all()
    )
    by_mount = {item.mount: item for item in states}
    observed = [by_mount.get(mount) for mount in configured]
    committed = [state for state in observed if state is not None and state.last_committed_at is not None]
    available = len(committed)
    if any(state is not None and state.status in {'stale', 'failed'} for state in observed):
        status = 'stale'
    elif available == len(configured) and all(state.status == 'ready' for state in committed):
        status = 'ready'
    elif available:
        status = 'partial'
    else:
        status = 'not_collected'

    timestamps: list[datetime] = [state.last_committed_at for state in committed if state.last_committed_at is not None]
    return {
        'state': status,
        'approved_mount_count': len(configured),
        'committed_mount_count': available,
        'observed_secret_count': sum(int(state.observed_count or 0) for state in committed) if committed else None,
        'last_committed_at': max(timestamps) if timestamps else None,
    }
