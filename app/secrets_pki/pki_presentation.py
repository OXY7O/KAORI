"""Aggregate read-only public PKI issuer readiness from committed KAORI state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_pki import PKIIssuerCollectionState
from app.models.vault import VaultInstance

MAX_VAULT_SOURCES = 25
MAX_PKI_SCOPES = 100


def pki_public_readiness(*, instance: VaultInstance | None = None) -> dict[str, Any]:
    """Bound all queries and show missing/stale sources as unknown, not zero."""
    if instance is None:
        sources = (
            VaultInstance.query.join(VaultInstance.integration_instance)
            .filter(
                IntegrationInstance.integration_type == 'secrets_pki',
                IntegrationInstance.provider_key == 'vault',
                IntegrationInstance.lifecycle_status == 'active',
                IntegrationInstance.enabled.is_(True),
            )
            .order_by(VaultInstance.id.asc())
            .limit(MAX_VAULT_SOURCES + 1)
            .all()
        )
    else:
        sources = [instance]
    if len(sources) > MAX_VAULT_SOURCES:
        return _result('blocked', 'Source Limit Exceeded')

    try:
        scopes = {
            (row.integration_instance_id, row.namespace or '', mount)
            for row in sources
            for mount in parse_approved_pki_mounts(','.join(row.pki_mounts or ()))
        }
    except ValueError:
        return _result('blocked', 'Invalid Approved PKI Mount Scope')
    if len(scopes) > MAX_PKI_SCOPES:
        return _result('blocked', 'PKI Mount Coverage Exceeds Limit')
    if not scopes:
        return _result('not_configured', 'PKI Collection Not Configured', approved_mounts=0)
    rows = PKIIssuerCollectionState.query.filter(
        PKIIssuerCollectionState.integration_instance_id.in_(
            [row.integration_instance_id for row in sources]
        )
    ).limit(MAX_PKI_SCOPES + 1).all()
    if len(rows) > MAX_PKI_SCOPES:
        return _result('blocked', 'PKI Collection State Exceeds Limit')
    selected = [
        item for item in rows
        if (item.integration_instance_id, item.provider_namespace, item.mount) in scopes
    ]
    committed = [item for item in selected if item.last_committed_at is not None]
    timestamps: list[datetime] = [
        item.last_committed_at for item in committed if item.last_committed_at is not None
    ]
    count = sum(int(item.observed_issuer_count or 0) for item in committed) if committed else None
    if not committed:
        state, label = 'not_collected', 'Public PKI Not Collected'
    elif any(item.status in {'failed', 'stale'} for item in selected):
        state, label = 'stale', 'Stale Public PKI Evidence'
    elif len(committed) < len(scopes):
        state, label = 'partial', 'Partial Public PKI Coverage'
    else:
        state, label = 'committed', 'Committed Public PKI Evidence'
    return _result(
        state, label, approved_mounts=len(scopes), committed_mounts=len(committed),
        observed_issuers=count, last_committed_at=max(timestamps) if timestamps else None,
    )


def _result(
    state: str, label: str, *, approved_mounts: int | None = None,
    committed_mounts: int | None = None, observed_issuers: int | None = None,
    last_committed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        'state': state, 'label': label,
        'approved_mounts': approved_mounts,
        'committed_mounts': committed_mounts,
        'observed_issuers': observed_issuers,
        'last_committed_at': last_committed_at,
        'has_evidence': committed_mounts is not None and committed_mounts > 0,
    }
