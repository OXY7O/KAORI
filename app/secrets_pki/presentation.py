"""Read-only Secrets & PKI operational summary from committed KAORI state.

No Vault calls, Secret paths, tokens, credential material or inferred trust
verdicts are included in any presentation contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretInventoryCollectionState
from app.models.vault import VaultInstance

MAX_FLEET_SOURCES = 25
MAX_FLEET_MOUNTS = MAX_FLEET_SOURCES * 8


def _display_update(last: datetime | None) -> str:
    if last is None:
        return 'Not Collected'
    observed = last if last.tzinfo else last.replace(tzinfo=UTC)
    minutes = max(int((datetime.now(UTC) - observed).total_seconds() // 60), 0)
    if minutes < 1:
        return 'Updated just now'
    if minutes < 60:
        return f'Updated {minutes}m ago'
    if minutes < 1440:
        return f'Updated {minutes // 60}h ago'
    return f'Updated {minutes // 1440}d ago'


def build_secrets_pki_operational_summary() -> dict[str, Any]:
    """Bounded fleet aggregation; source details remain separately authorized."""
    query = (
        VaultInstance.query.join(VaultInstance.integration_instance)
        .filter(
            IntegrationInstance.integration_type == 'secrets_pki',
            IntegrationInstance.provider_key == 'vault',
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationInstance.enabled.is_(True),
        )
        .order_by(VaultInstance.id.asc())
    )
    sources = query.limit(MAX_FLEET_SOURCES + 1).all()
    if len(sources) > MAX_FLEET_SOURCES:
        return {
            'state': 'blocked',
            'label': 'Fleet Scope Exceeds Limit',
            'tone': 'warning',
            'provider_count': None,
            'approved_mount_count': None,
            'committed_mount_count': None,
            'observed_secret_count': None,
            'last_committed_at': None,
            'updated_label': 'Not Collected',
            'has_evidence': False,
            'source_limit_exceeded': True,
        }
    scopes = {
        (int(row.integration_instance_id), row.namespace or '', mount)
        for row in sources
        for mount in (row.kv2_mounts or ())
        if isinstance(mount, str) and mount
    }
    if len(scopes) > MAX_FLEET_MOUNTS:
        raise ValueError('Secrets & PKI approved inventory source scope exceeds its collection bound.')
    state_rows = (
        SecretInventoryCollectionState.query.filter(
            SecretInventoryCollectionState.integration_instance_id.in_([row.integration_instance_id for row in sources])
        )
        .limit(MAX_FLEET_MOUNTS + 1)
        .all()
        if sources
        else []
    )
    if len(state_rows) > MAX_FLEET_MOUNTS:
        return {
            'state': 'blocked',
            'label': 'Inventory Coverage Exceeds Limit',
            'tone': 'warning',
            'provider_count': len(sources),
            'approved_mount_count': len(scopes),
            'committed_mount_count': None,
            'observed_secret_count': None,
            'last_committed_at': None,
            'updated_label': 'Not Collected',
            'has_evidence': False,
            'source_limit_exceeded': True,
        }
    selected = [row for row in state_rows if (row.integration_instance_id, row.provider_namespace, row.mount) in scopes]
    committed = [row for row in selected if row.last_committed_at is not None]
    last = max(
        (row.last_committed_at for row in committed if row.last_committed_at is not None),
        default=None,
    )
    total = sum(int(row.observed_count or 0) for row in committed) if committed else None
    if not sources or not scopes:
        state, label = 'blocked', 'Inventory Setup Required'
    elif not committed:
        state, label = 'not_collected', 'Inventory Not Collected'
    elif any(row.status in {'stale', 'failed'} for row in selected):
        state, label = 'stale', 'Stale Collection Evidence'
    elif len(committed) < len(scopes):
        state, label = 'partial', 'Partial Inventory Coverage'
    else:
        state, label = 'committed', 'Committed Inventory Evidence'
    return {
        'state': state,
        'label': label,
        'tone': 'normal' if state == 'committed' else 'warning',
        'provider_count': len(sources),
        'approved_mount_count': len(scopes),
        'committed_mount_count': len(committed),
        'observed_secret_count': total,
        'last_committed_at': last,
        'updated_label': _display_update(last),
        'has_evidence': bool(committed),
        'source_limit_exceeded': False,
    }
