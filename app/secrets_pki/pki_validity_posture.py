"""Public stored Vault PKI certificate validity windows from committed evidence.

This does not attest certificate trust, revocation, issuance completeness,
consumer adoption or endpoint TLS serving. No Vault/HTTP read on page render.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect, select, tuple_
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.models.vault import VaultInstance

_MAX_SOURCES = 25
_MAX_SCOPES = 100
_MAX_CERTS_PER_MOUNT = 64
_MAX_CERTS = _MAX_SCOPES * _MAX_CERTS_PER_MOUNT
_FRESHNESS = timedelta(hours=24)
_STATES = ('within_validity_window', 'not_yet_valid', 'expired', 'unknown')
_EXPIRY_BANDS = ('expires_within_7d', 'expires_8_to_30d', 'expires_after_30d')
_EXPIRY_7D = timedelta(days=7)
_EXPIRY_30D = timedelta(days=30)


def _result(
    status: str,
    label: str,
    *,
    counts: Counter[str] | None = None,
    expiry_counts: Counter[str] | None = None,
    count: int | None = None,
    last_observed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        'status': status,
        'label': label,
        'observed_stored_certificates': count,
        **{state: (counts.get(state, 0) if counts is not None else None) for state in _STATES},
        **{band: (expiry_counts.get(band, 0) if expiry_counts is not None else None) for band in _EXPIRY_BANDS},
        'last_observed_at': last_observed_at,
        'expiry_band_basis': 'UTC current-generation public X.509 validity only',
        'coverage': 'Opted-in committed Vault PKI stored certificates only',
        'trust_verified': False,
        'revocation_verified': False,
        'endpoint_serving_verified': False,
    }


def _utc(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    # Committed SQLAlchemy UTC DateTime values are naive on SQLite as well as
    # PostgreSQL configurations without timezone translation.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _schema_ready() -> bool:
    required = {
        'vault_instances',
        'integration_instances',
        'secrets_pki_stored_cert_observations',
        'secrets_pki_stored_cert_collection_states',
    }
    return required.issubset(set(inspect(db.engine).get_table_names()))


def _collection_state_incomplete(row: Any, *, instant: datetime) -> bool:
    """Reject an incomplete or stale committed collection generation."""
    observed, committed = _utc(row[5]), _utc(row[6])
    return (
        row[3] != 'ready'
        or type(row[4]) is not int
        or not 0 <= row[4] <= _MAX_CERTS_PER_MOUNT
        or observed is None
        or committed is None
        or not timedelta(0) <= instant - observed <= _FRESHNESS
        or not timedelta(0) <= instant - committed <= _FRESHNESS
    )


def _record_validity_window(
    row: Any, *, instant: datetime, counts: Counter[str], expiry: Counter[str]
) -> None:
    """Classify a single public X.509 window without asserting trust or revocation."""
    valid_from, valid_until = _utc(row[3]), _utc(row[4])
    if valid_from is None or valid_until is None or valid_from >= valid_until:
        counts['unknown'] += 1
    elif instant < valid_from:
        counts['not_yet_valid'] += 1
    elif instant >= valid_until:
        counts['expired'] += 1
    else:
        counts['within_validity_window'] += 1
        remaining = valid_until - instant
        if remaining <= _EXPIRY_7D:
            expiry['expires_within_7d'] += 1
        elif remaining <= _EXPIRY_30D:
            expiry['expires_8_to_30d'] += 1
        else:
            expiry['expires_after_30d'] += 1


def build_stored_pki_validity_posture(*, now: datetime | None = None) -> dict[str, Any]:
    """Require source-complete current observations before exposing any counts."""
    instant = _utc(now or datetime.now(UTC))
    if instant is None:
        return _result('unavailable', 'PKI Validity Evidence Unavailable')
    try:
        if not _schema_ready():
            return _result('unavailable', 'PKI Validity Schema Not Ready')
        sources = db.session.execute(
            select(
                IntegrationInstance.id,
                IntegrationInstance.readiness_status,
                VaultInstance.namespace,
                VaultInstance.pki_mounts,
                VaultInstance.pki_stored_certs_enabled,
            )
            .join(VaultInstance, VaultInstance.integration_instance_id == IntegrationInstance.id)
            .where(
                IntegrationInstance.integration_type == 'secrets_pki',
                IntegrationInstance.provider_key == 'vault',
                IntegrationInstance.lifecycle_status == 'active',
                IntegrationInstance.enabled.is_(True),
            )
            .order_by(IntegrationInstance.id.asc())
            .limit(_MAX_SOURCES + 1)
        ).all()
        if len(sources) > _MAX_SOURCES:
            return _result('blocked', 'PKI Source Limit Exceeded')
        scopes = {
            (source.id, source.namespace or '', mount)
            for source in sources
            if source.pki_stored_certs_enabled
            for mount in parse_approved_pki_mounts(','.join(source.pki_mounts or ()))
        }
        if not scopes:
            return _result('not_configured', 'PKI Stored Certificates Not Enabled')
        if len(scopes) > _MAX_SCOPES:
            return _result('blocked', 'PKI Approved Scope Limit Exceeded')
        if any(source.readiness_status != 'ready' for source in sources if source.pki_stored_certs_enabled):
            return _result('unavailable', 'PKI Provider Validation Required')
        states = db.session.execute(
            select(
                PKIStoredCertificateCollectionState.integration_instance_id,
                PKIStoredCertificateCollectionState.provider_namespace,
                PKIStoredCertificateCollectionState.mount,
                PKIStoredCertificateCollectionState.status,
                PKIStoredCertificateCollectionState.observed_stored_certificate_count,
                PKIStoredCertificateCollectionState.last_observed_at,
                PKIStoredCertificateCollectionState.last_committed_at,
            )
            .where(PKIStoredCertificateCollectionState.integration_instance_id.in_([source.id for source in sources]))
            .limit(_MAX_SCOPES + 1)
        ).all()
        if len(states) > _MAX_SCOPES:
            return _result('blocked', 'PKI Collection State Limit Exceeded')
        state_by_scope = {(row[0], row[1], row[2]): row for row in states if (row[0], row[1], row[2]) in scopes}
        if set(state_by_scope) != scopes:
            return _result('incomplete', 'PKI Collection Coverage Incomplete')
        for row in state_by_scope.values():
            if _collection_state_incomplete(row, instant=instant):
                return _result('incomplete', 'PKI Validity Evidence Incomplete or Stale')
        rows = db.session.execute(
            select(
                PKIStoredCertificateObservation.integration_instance_id,
                PKIStoredCertificateObservation.provider_namespace,
                PKIStoredCertificateObservation.mount,
                PKIStoredCertificateObservation.valid_from,
                PKIStoredCertificateObservation.valid_until,
                PKIStoredCertificateObservation.last_observed_at,
            )
            .where(
                tuple_(
                    PKIStoredCertificateObservation.integration_instance_id,
                    PKIStoredCertificateObservation.provider_namespace,
                    PKIStoredCertificateObservation.mount,
                ).in_(sorted(scopes)),
                PKIStoredCertificateObservation.observation_status == 'observed',
            )
            .limit(_MAX_CERTS + 1)
        ).all()
        if len(rows) > _MAX_CERTS:
            return _result('blocked', 'PKI Stored Certificate Limit Exceeded')
        counts_by_scope = Counter((row[0], row[1], row[2]) for row in rows)
        if any(counts_by_scope.get(scope, 0) != state_by_scope[scope][4] for scope in scopes):
            return _result('incomplete', 'PKI Committed Certificate Count Conflict')
        result: Counter[str] = Counter()
        expiry: Counter[str] = Counter()
        for row in rows:
            source = state_by_scope[(row[0], row[1], row[2])]
            if _utc(row[5]) != _utc(source[5]):
                return _result('incomplete', 'PKI Certificate Generation Mismatch')
            _record_validity_window(row, instant=instant, counts=result, expiry=expiry)
        return _result(
            'ready',
            'Qualified Stored Certificate Validity Windows',
            counts=result,
            expiry_counts=expiry,
            count=len(rows),
            last_observed_at=max(_utc(row[5]) for row in state_by_scope.values()),
        )
    except (SQLAlchemyError, TypeError, ValueError, AttributeError):
        return _result('unavailable', 'PKI Validity Evidence Unavailable')
