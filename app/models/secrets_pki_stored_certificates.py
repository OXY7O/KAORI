"""Observed stored Vault PKI certificates, not a complete issuance register."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class PKIStoredCertificateObservation(db.Model):
    __tablename__ = 'secrets_pki_stored_cert_observations'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id',
            'provider_namespace',
            'mount',
            'serial_hex',
            name='uq_secrets_pki_stored_cert_source_serial',
        ),
        Index(
            'ix_secrets_pki_stored_cert_scope',
            'integration_instance_id',
            'provider_namespace',
            'mount',
            'last_observed_at',
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
    serial_hex: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_status: Mapped[str] = mapped_column(String(30), nullable=False, default='observed')
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PKIStoredCertificateCollectionState(db.Model):
    __tablename__ = 'secrets_pki_stored_cert_collection_states'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount', name='uq_secrets_pki_stored_cert_collection_scope'
        ),
        Index('ix_spki_stored_cert_state_instance', 'integration_instance_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'),
        nullable=False,
    )
    provider_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    mount: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    observed_stored_certificate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(250), nullable=True)
