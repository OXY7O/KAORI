"""Atomic, source-qualified reconciliation of *stored* public Vault PKI certificates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_stored_certificates import (
    MAX_STORED_CERTIFICATES,
    StoredCertificateCollection,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.models.vault import VaultInstance


@dataclass(frozen=True, slots=True)
class StoredCertificateCommitSummary:
    observed_count: int
    not_observed_count: int
    committed_at: datetime


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('PKI certificate observation time must include a timezone.')
    return value.astimezone(UTC)


def _hex(value: str, *, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(char not in '0123456789abcdef' for char in value)
    ):
        raise ValueError('PKI public serial/fingerprint is malformed.')
    return value


def _validate(snapshot: StoredCertificateCollection) -> None:
    if (
        snapshot.complete is not True
        or snapshot.coverage != 'vault_stored_only'
        or not 0 <= len(snapshot.certificates) <= MAX_STORED_CERTIFICATES
        or len(parse_approved_pki_mounts(snapshot.mount)) != 1
    ):
        raise ValueError('Stored PKI collection is incomplete or scope is unsupported.')
    _aware(snapshot.observed_at)
    observed: set[str] = set()
    for row in snapshot.certificates:
        serial = _hex(row.serial_hex, maximum=100)
        if serial in observed:
            raise ValueError('Duplicate stored certificate serial in source observation.')
        observed.add(serial)
        cert = row.certificate
        if (
            _hex(cert.fingerprint_sha256, maximum=64) != cert.fingerprint_sha256
            or len(cert.fingerprint_sha256) != 64
            or int(serial, 16) != int(_hex(cert.serial_hex, maximum=100), 16)
            or _aware(cert.valid_until) <= _aware(cert.valid_from)
        ):
            raise ValueError('Stored public certificate facts are malformed.')


def commit_stored_pki_certificates(
    integration_instance_id: int,
    evidence: StoredCertificateCollection,
) -> StoredCertificateCommitSummary:
    """One complete authorized mount commit; never infer unlisted certificate revocation."""
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
        if (
            identity is None
            or provider is None
            or identity.integration_type != 'secrets_pki'
            or identity.provider_key != 'vault'
            or identity.lifecycle_status != 'active'
            or not identity.enabled
            or identity.readiness_status != 'ready'
            or not provider.pki_stored_certs_enabled
            or evidence.mount not in parse_approved_pki_mounts(','.join(provider.pki_mounts or ()))
        ):
            raise ValueError('Stored Vault PKI source is not eligible for committed reconciliation.')
        namespace = provider.namespace or ''
        state = db.session.execute(
            select(PKIStoredCertificateCollectionState)
            .where(
                PKIStoredCertificateCollectionState.integration_instance_id == integration_instance_id,
                PKIStoredCertificateCollectionState.provider_namespace == namespace,
                PKIStoredCertificateCollectionState.mount == evidence.mount,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if state is None:
            state = PKIStoredCertificateCollectionState()
            state.integration_instance_id = integration_instance_id
            state.provider_namespace = namespace
            state.mount = evidence.mount
            db.session.add(state)
            db.session.flush()
        timestamp = _aware(evidence.observed_at)
        if state.last_observed_at is not None and timestamp < _aware(state.last_observed_at):
            raise ValueError('Out-of-order stored PKI observation cannot replace newer evidence.')
        if not evidence.certificates and (state.observed_stored_certificate_count or 0) > 0:
            raise ValueError('Unexpected empty stored certificate list cannot erase committed history.')
        rows = (
            db.session.execute(
                select(PKIStoredCertificateObservation)
                .where(
                    PKIStoredCertificateObservation.integration_instance_id == integration_instance_id,
                    PKIStoredCertificateObservation.provider_namespace == namespace,
                    PKIStoredCertificateObservation.mount == evidence.mount,
                )
                .with_for_update()
            )
            .scalars()
            .all()
        )
        by_serial = {item.serial_hex: item for item in rows}
        observed: set[str] = set()
        for source in evidence.certificates:
            serial = source.serial_hex
            certificate = source.certificate
            observed.add(serial)
            entry = by_serial.get(serial)
            if entry is None:
                entry = PKIStoredCertificateObservation()
                entry.integration_instance_id = integration_instance_id
                entry.provider_namespace = namespace
                entry.mount = evidence.mount
                entry.serial_hex = serial
                entry.fingerprint_sha256 = certificate.fingerprint_sha256
                entry.valid_from = _aware(certificate.valid_from)
                entry.valid_until = _aware(certificate.valid_until)
                db.session.add(entry)
            elif (
                entry.fingerprint_sha256 != certificate.fingerprint_sha256
                or _aware(entry.valid_from) != _aware(certificate.valid_from)
                or _aware(entry.valid_until) != _aware(certificate.valid_until)
            ):
                raise ValueError('Stored certificate immutable serial/fingerprint conflict.')
            entry.observation_status = 'observed'
            entry.last_observed_at = timestamp
        missing = 0
        for entry in rows:
            if entry.serial_hex not in observed:
                entry.observation_status = 'not_observed'
                missing += 1
        state.status = 'ready'
        state.observed_stored_certificate_count = len(observed)
        state.last_observed_at = timestamp
        committed = datetime.now(UTC)
        state.last_committed_at = committed
        state.last_error = None
        db.session.commit()
        return StoredCertificateCommitSummary(len(observed), missing, committed)
    except Exception:
        db.session.rollback()
        raise


def mark_stored_pki_certificates_failed(integration_instance_id: int, mount: str) -> None:
    """Record only sanitized failure, preserving prior authoritative PKI history."""
    try:
        if len(parse_approved_pki_mounts(mount)) != 1:
            return
        provider = VaultInstance.query.filter_by(integration_instance_id=integration_instance_id).first()
        if provider is None or not provider.pki_stored_certs_enabled:
            return
        try:
            approved = parse_approved_pki_mounts(','.join(provider.pki_mounts or ()))
        except ValueError:
            return
        if mount not in approved:
            return
        state = PKIStoredCertificateCollectionState.query.filter_by(
            integration_instance_id=integration_instance_id,
            provider_namespace=provider.namespace or '',
            mount=mount,
        ).first()
        if state is None:
            state = PKIStoredCertificateCollectionState()
            state.integration_instance_id = integration_instance_id
            state.provider_namespace = provider.namespace or ''
            state.mount = mount
            db.session.add(state)
        state.status = 'stale' if state.last_committed_at else 'failed'
        state.last_error = 'Stored PKI certificate collection unavailable; prior history retained.'
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
