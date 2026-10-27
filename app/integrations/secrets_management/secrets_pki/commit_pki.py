"""Atomic committed public Vault PKI evidence, with per-mount admission locks.

Never store public certificate PEM, DN/SAN, issuer names, Secret material,
tokens, CA keys, provider error bodies or unqualified revocation/trust claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from string import hexdigits
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    MAX_ISSUERS,
    PKIIssuerCollection,
    parse_approved_pki_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_pki import (
    PKIIssuerCollectionState,
    PKIIssuerIdentity,
    PKIPublicCertificateObservation,
)
from app.models.vault import VaultInstance

MAX_CERTIFICATE_CHAIN = 8


@dataclass(frozen=True, slots=True)
class PKICommitSummary:
    observed_issuer_count: int
    observed_certificate_count: int
    not_observed_issuer_count: int
    committed_at: datetime


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('Public PKI observation must have timezone-qualified time.')
    return value.astimezone(UTC)


def _fingerprint(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('PKI public certificate fingerprint is malformed.')
    return value


def _validate(evidence: PKIIssuerCollection) -> None:
    if evidence.complete is not True or not 0 <= len(evidence.issuers) <= MAX_ISSUERS:
        raise ValueError('PKI issuer observation is incomplete or outside bounds.')
    _utc(evidence.observed_at)
    if len(parse_approved_pki_mounts(evidence.mount)) != 1:
        raise ValueError('PKI committed scope must be one explicit approved mount.')
    ids: set[str] = set()
    for item in evidence.issuers:
        try:
            provider_id = str(UUID(item.issuer_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError('Public PKI issuer identity is malformed.') from exc
        if provider_id != item.issuer_id or provider_id in ids:
            raise ValueError('Duplicate or noncanonical PKI issuer source identity.')
        ids.add(provider_id)
        cert = item.certificate
        _fingerprint(cert.fingerprint_sha256)
        if (
            not isinstance(cert.serial_hex, str)
            or not 1 <= len(cert.serial_hex) <= 100
            or any(char not in hexdigits.lower() for char in cert.serial_hex)
        ):
            raise ValueError('PKI public certificate serial is malformed.')
        if _utc(cert.valid_until) <= _utc(cert.valid_from):
            raise ValueError('PKI certificate validity interval is invalid.')
        if not isinstance(cert.self_issued, bool) or cert.is_ca not in {True, False, None}:
            raise ValueError('PKI certificate public CA evidence is malformed.')
        if len(item.chain_fingerprints) > MAX_CERTIFICATE_CHAIN or any(
            not isinstance(x, str) or len(x) != 64 or _fingerprint(x) != x for x in item.chain_fingerprints
        ):
            raise ValueError('PKI public CA chain exceeds the safe evidence contract.')
        if item.trust_status != 'not_evaluated' or item.revocation_status != 'not_evaluated':
            raise ValueError('PKI source adapter cannot attest trust or revocation.')


def _is_eligible_pki_source(
    identity: IntegrationInstance,
    provider: VaultInstance,
    mount: str,
) -> bool:
    """Qualify the locked Vault PKI identity and currently approved mount."""
    return (
        identity.integration_type == 'secrets_pki'
        and identity.provider_key == 'vault'
        and identity.lifecycle_status == 'active'
        and identity.enabled
        and identity.readiness_status == 'ready'
        and mount in parse_approved_pki_mounts(','.join(provider.pki_mounts or ()))
    )


def commit_pki_public_issuers(
    integration_instance_id: int,
    evidence: PKIIssuerCollection,
) -> PKICommitSummary:
    """Commit an entire approved mount or nothing; never delete historic evidence."""
    _validate(evidence)
    try:
        identity = db.session.execute(
            select(IntegrationInstance).where(IntegrationInstance.id == integration_instance_id).with_for_update()
        ).scalar_one_or_none()
        provider = db.session.execute(
            select(VaultInstance)
            .where(VaultInstance.integration_instance_id == integration_instance_id)
            .with_for_update(of=VaultInstance)
        ).scalar_one_or_none()
        if identity is None or provider is None or not _is_eligible_pki_source(identity, provider, evidence.mount):
            raise ValueError('Vault PKI source is not eligible for committed collection.')
        namespace = provider.namespace or ''
        state = db.session.execute(
            select(PKIIssuerCollectionState)
            .where(
                PKIIssuerCollectionState.integration_instance_id == integration_instance_id,
                PKIIssuerCollectionState.provider_namespace == namespace,
                PKIIssuerCollectionState.mount == evidence.mount,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if state is None:
            state = PKIIssuerCollectionState()
            state.integration_instance_id = integration_instance_id
            state.provider_namespace = namespace
            state.mount = evidence.mount
            db.session.add(state)
            db.session.flush()
        if not evidence.issuers and (state.observed_issuer_count or 0) > 0:
            raise ValueError('Unexpected empty PKI collection cannot replace earlier committed issuer history.')
        existing = (
            db.session.execute(
                select(PKIIssuerIdentity)
                .where(
                    PKIIssuerIdentity.integration_instance_id == integration_instance_id,
                    PKIIssuerIdentity.provider_namespace == namespace,
                    PKIIssuerIdentity.mount == evidence.mount,
                )
                .options(selectinload(PKIIssuerIdentity.certificates))
                .with_for_update()
            )
            .scalars()
            .all()
        )
        by_source = {row.provider_issuer_id: row for row in existing}
        timestamp = _utc(evidence.observed_at)
        if state.last_observed_at is not None and timestamp < _utc(state.last_observed_at):
            raise ValueError('Out-of-order PKI observation cannot overwrite newer evidence.')
        observed: set[str] = set()
        certificates = 0
        for item in evidence.issuers:
            observed.add(item.issuer_id)
            issuer = by_source.get(item.issuer_id)
            if issuer is None:
                issuer = PKIIssuerIdentity()
                issuer.integration_instance_id = integration_instance_id
                issuer.provider_namespace = namespace
                issuer.mount = evidence.mount
                issuer.provider_issuer_id = item.issuer_id
                db.session.add(issuer)
                by_source[item.issuer_id] = issuer
                db.session.flush()
            issuer.observation_status = 'observed'
            issuer.last_observed_at = timestamp
            known = {c.fingerprint_sha256: c for c in issuer.certificates}
            current = item.certificate
            certificate = known.get(current.fingerprint_sha256)
            if certificate is None:
                certificate = PKIPublicCertificateObservation()
                certificate.issuer_identity_id = issuer.id
                certificate.fingerprint_sha256 = current.fingerprint_sha256
                certificate.serial_hex = current.serial_hex
                certificate.valid_from = _utc(current.valid_from)
                certificate.valid_until = _utc(current.valid_until)
                certificate.is_ca = current.is_ca
                certificate.self_issued = current.self_issued
                certificate.chain_fingerprints = ','.join(item.chain_fingerprints)
                db.session.add(certificate)
            else:
                if (
                    certificate.serial_hex != current.serial_hex
                    or _utc(certificate.valid_from) != _utc(current.valid_from)
                    or _utc(certificate.valid_until) != _utc(current.valid_until)
                    or certificate.is_ca != current.is_ca
                    or certificate.self_issued != current.self_issued
                    or certificate.chain_fingerprints != ','.join(item.chain_fingerprints)
                ):
                    raise ValueError('Immutable public PKI certificate fingerprint conflicts with prior evidence.')
            certificate.observation_status = 'observed'
            certificate.last_observed_at = timestamp
            for previous in known.values():
                if previous.fingerprint_sha256 != current.fingerprint_sha256:
                    previous.observation_status = 'historical'
            certificates += 1
        missing = 0
        for issuer in existing:
            if issuer.provider_issuer_id not in observed:
                issuer.observation_status = 'not_observed'
                # Historical public fingerprints remain durable, but may not
                # be reported as currently observed after the issuer vanishes.
                for certificate in issuer.certificates:
                    certificate.observation_status = 'not_observed'
                missing += 1
        state.status = 'ready'
        state.observed_issuer_count = len(observed)
        state.last_observed_at = timestamp
        committed_at = datetime.now(UTC)
        state.last_committed_at = committed_at
        state.last_error = None
        db.session.commit()
        return PKICommitSummary(len(observed), certificates, missing, committed_at)
    except Exception:
        db.session.rollback()
        raise


def mark_pki_public_issuers_failed(integration_instance_id: int, mount: str) -> None:
    """Only a sanitized freshness transition; never remove committed PKI facts."""
    try:
        configured = parse_approved_pki_mounts(mount)
        if len(configured) != 1:
            return
        provider = VaultInstance.query.filter_by(integration_instance_id=integration_instance_id).first()
        if provider is None:
            return
        try:
            approved = parse_approved_pki_mounts(','.join(provider.pki_mounts or ()))
        except ValueError:
            # Concurrent configuration invalidation must not raise from the
            # sanitized worker failure-recording path.
            return
        if mount not in approved:
            return
        namespace = provider.namespace or ''
        state = PKIIssuerCollectionState.query.filter_by(
            integration_instance_id=integration_instance_id,
            provider_namespace=namespace,
            mount=mount,
        ).first()
        if state is None:
            state = PKIIssuerCollectionState()
            state.integration_instance_id = integration_instance_id
            state.provider_namespace = namespace
            state.mount = mount
            db.session.add(state)
        state.status = 'stale' if state.last_committed_at is not None else 'failed'
        state.last_error = 'PKI public issuer collection unavailable; retained evidence unchanged.'
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
