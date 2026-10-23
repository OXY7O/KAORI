"""Bounded read-only readiness for source-limited Vault stored certificates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import PKIStoredCertificateCollectionState
from app.models.vault import VaultInstance
from app.secrets_pki.pki_collection_freshness import qualified_committed_pki_count

MAX_VAULT_SOURCES = 25
MAX_PKI_SCOPES = 100


def stored_pki_certificate_readiness(
    *, instance: VaultInstance | None = None, now: datetime | None = None,
) -> dict[str, Any]:
    """Counts are scoped to successful LIST /certs, never entire issued population."""
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
            .limit(MAX_VAULT_SOURCES + 1).all()
        )
    else:
        sources = [instance]
    if len(sources) > MAX_VAULT_SOURCES:
        return _result('blocked', 'Vault Source Limit Exceeded')
    try:
        scopes = {
            (row.integration_instance_id, row.namespace or '', mount)
            for row in sources
            if row.pki_stored_certs_enabled
            for mount in parse_approved_pki_mounts(','.join(row.pki_mounts or ()))
        }
    except ValueError:
        return _result('blocked', 'Invalid Approved PKI Scope')
    if len(scopes) > MAX_PKI_SCOPES:
        return _result('blocked', 'Stored Certificate Scope Exceeds Limit')
    if not scopes:
        return _result('not_configured', 'Stored Certificate Collection Not Enabled',
                       approved_mounts=0)
    state_rows = PKIStoredCertificateCollectionState.query.filter(
        PKIStoredCertificateCollectionState.integration_instance_id.in_(
            [row.integration_instance_id for row in sources]
        )
    ).limit(MAX_PKI_SCOPES + 1).all()
    if len(state_rows) > MAX_PKI_SCOPES:
        return _result('blocked', 'Stored Certificate State Exceeds Limit')
    matching = [
        item for item in state_rows
        if (item.integration_instance_id, item.provider_namespace, item.mount) in scopes
    ]
    counts = [
        qualified_committed_pki_count(
            item, instant=instant,
            count_field='observed_stored_certificate_count', max_count=64,
        )
        for item in matching
    ]
    unvalidated = any(
        source.integration_instance.readiness_status != 'ready'
        or not source.integration_instance.enabled
        or source.integration_instance.lifecycle_status != 'active'
        or source.integration_instance.integration_type != 'secrets_pki'
        or source.integration_instance.provider_key != 'vault'
        for source in sources
    )
    if not matching:
        state, label = (
            ('blocked', 'Vault Validation Required') if unvalidated
            else ('not_collected', 'Stored Certificates Not Collected')
        )
    elif unvalidated:
        state, label = 'stale', 'Vault Validation Required'
    elif len(matching) != len(scopes):
        state, label = 'partial', 'Partial Stored Certificate Coverage'
    elif any(count is None for count in counts):
        state, label = 'stale', 'Stale or Incomplete Stored Certificate Evidence'
    else:
        state, label = 'committed', 'Committed Stored Certificate Evidence'
    qualified = state == 'committed'
    return _result(
        state, label, approved_mounts=len(scopes),
        committed_mounts=len(matching) if qualified else None,
        observed_certificates=sum(value for value in counts if value is not None) if qualified else None,
        last_committed_at=max(item.last_committed_at for item in matching) if qualified else None,
    )


def _result(
    state: str, label: str, *,
    approved_mounts: int | None = None, committed_mounts: int | None = None,
    observed_certificates: int | None = None,
    last_committed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        'state': state, 'label': label, 'approved_mounts': approved_mounts,
        'committed_mounts': committed_mounts,
        'observed_certificates': observed_certificates,
        'last_committed_at': last_committed_at,
        'coverage': 'vault_stored_only',
    }
