"""Aggregate read-only public PKI issuer readiness from committed KAORI state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    MAX_ISSUERS,
    parse_approved_pki_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_pki import PKIIssuerCollectionState
from app.models.vault import VaultInstance
from app.secrets_pki.pki_collection_freshness import qualified_committed_pki_count

MAX_VAULT_SOURCES = 25
MAX_PKI_SCOPES = 100


def pki_public_readiness(
    *,
    instance: VaultInstance | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Bound all queries and show missing/stale sources as unknown, not zero."""
    instant = now or datetime.now(UTC)
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
    any_unvalidated = any(
        row.integration_instance.readiness_status != 'ready'
        or not row.integration_instance.enabled
        or row.integration_instance.lifecycle_status != 'active'
        or row.integration_instance.integration_type != 'secrets_pki'
        or row.integration_instance.provider_key != 'vault'
        for row in sources
    )

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
    rows = (
        PKIIssuerCollectionState.query.filter(
            PKIIssuerCollectionState.integration_instance_id.in_([row.integration_instance_id for row in sources])
        )
        .limit(MAX_PKI_SCOPES + 1)
        .all()
    )
    if len(rows) > MAX_PKI_SCOPES:
        return _result('blocked', 'PKI Collection State Exceeds Limit')
    selected = [item for item in rows if (item.integration_instance_id, item.provider_namespace, item.mount) in scopes]
    counts = [
        qualified_committed_pki_count(
            item,
            instant=instant,
            count_field='observed_issuer_count',
            max_count=MAX_ISSUERS,
        )
        for item in selected
    ]
    if not selected:
        state, label = (
            ('blocked', 'PKI Provider Validation Required')
            if any_unvalidated
            else ('not_collected', 'Public PKI Not Collected')
        )
    elif any_unvalidated:
        state, label = 'stale', 'Vault PKI Provider Validation Required'
    elif len(selected) != len(scopes):
        state, label = 'partial', 'Partial Public PKI Coverage'
    elif any(count is None for count in counts):
        state, label = 'stale', 'Stale or Incomplete Public PKI Evidence'
    else:
        state, label = 'committed', 'Committed Public PKI Evidence'
    qualified = state == 'committed'
    return _result(
        state,
        label,
        approved_mounts=len(scopes),
        committed_mounts=len(selected) if qualified else None,
        observed_issuers=sum(value for value in counts if value is not None) if qualified else None,
        last_committed_at=max(item.last_committed_at for item in selected) if qualified else None,
    )


def _result(
    state: str,
    label: str,
    *,
    approved_mounts: int | None = None,
    committed_mounts: int | None = None,
    observed_issuers: int | None = None,
    last_committed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        'state': state,
        'label': label,
        'approved_mounts': approved_mounts,
        'committed_mounts': committed_mounts,
        'observed_issuers': observed_issuers,
        'last_committed_at': last_committed_at,
        'has_evidence': state == 'committed',
    }
