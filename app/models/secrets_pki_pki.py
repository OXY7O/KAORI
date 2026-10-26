"""Committed public Vault PKI issuer and certificate evidence only.

No certificate PEM, subject, SAN, private key, path metadata, credentials or
provider error responses are persisted in these models.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class PKIIssuerIdentity(db.Model):
    __tablename__ = 'secrets_pki_issuer_identities'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id',
            'provider_namespace',
            'mount',
            'provider_issuer_id',
            name='uq_secrets_pki_issuer_source',
        ),
        Index(
            'ix_secrets_pki_issuer_scope', 'integration_instance_id', 'provider_namespace', 'mount', 'last_observed_at'
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    provider_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    mount: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_issuer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    observation_status: Mapped[str] = mapped_column(String(30), nullable=False, default='observed')
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    certificates: Mapped[list[PKIPublicCertificateObservation]] = relationship(
        'PKIPublicCertificateObservation',
        back_populates='issuer',
        order_by='PKIPublicCertificateObservation.id',
        passive_deletes=True,
    )


class PKIPublicCertificateObservation(db.Model):
    __tablename__ = 'secrets_pki_public_certificates'
    __table_args__ = (
        UniqueConstraint('issuer_identity_id', 'fingerprint_sha256', name='uq_secrets_pki_public_cert_issuer_fp'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_identity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('secrets_pki_issuer_identities.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    serial_hex: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_ca: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    self_issued: Mapped[bool] = mapped_column(Boolean, nullable=False)
    chain_fingerprints: Mapped[str] = mapped_column(String(520), nullable=False, default='')
    observation_status: Mapped[str] = mapped_column(String(30), nullable=False, default='observed')
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    issuer: Mapped[PKIIssuerIdentity] = relationship(
        'PKIIssuerIdentity',
        back_populates='certificates',
    )


class PKIIssuerCollectionState(db.Model):
    __tablename__ = 'secrets_pki_pki_collection_states'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount', name='uq_secrets_pki_pki_collection_scope'
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    provider_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    mount: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    observed_issuer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(250), nullable=True)
