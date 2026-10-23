"""Provider-neutral Secret identities and Vault KV v2 metadata representations.

Secret material never belongs to these models. A Vault mount/path is a
representation identity, not an immutable KAORI Secret identity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class SecretIdentity(db.Model):
    __tablename__ = 'secrets_pki_secret_identities'

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4()),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default='discovered',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )


class SecretProviderRepresentation(db.Model):
    __tablename__ = 'secrets_pki_secret_representations'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount', 'path_sha256',
            name='uq_secrets_pki_provider_representation',
        ),
        Index(
            'ix_secrets_pki_representation_scope', 'integration_instance_id',
            'provider_namespace', 'mount', 'last_observed_at',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secret_identity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('secrets_pki_secret_identities.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    mount: Mapped[str] = mapped_column(String(160), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    path_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    representation_role: Mapped[str] = mapped_column(
        String(40), nullable=False, default='material_authority',
    )
    observation_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default='observed',
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    oldest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_versions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cas_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    secret_identity: Mapped[SecretIdentity] = relationship('SecretIdentity')
    versions: Mapped[list[SecretVersionObservation]] = relationship(
        'SecretVersionObservation', back_populates='representation',
        order_by='SecretVersionObservation.version',
        cascade='all, delete-orphan', passive_deletes=True,
    )


class SecretVersionObservation(db.Model):
    __tablename__ = 'secrets_pki_secret_versions'
    __table_args__ = (
        UniqueConstraint('representation_id', 'version', name='uq_secrets_pki_representation_version'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    representation_id: Mapped[int] = mapped_column(
        ForeignKey('secrets_pki_secret_representations.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_created_time: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_deletion_time: Mapped[str | None] = mapped_column(String(80), nullable=True)
    destroyed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    representation: Mapped[SecretProviderRepresentation] = relationship(
        'SecretProviderRepresentation', back_populates='versions',
    )


class SecretInventoryCollectionState(db.Model):
    __tablename__ = 'secrets_pki_inventory_collection_states'
    __table_args__ = (
        UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount',
            name='uq_secrets_pki_inventory_scope',
        ),
        Index('ix_spki_inventory_state_instance', 'integration_instance_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'),
        nullable=False,
    )
    provider_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    mount: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='not_collected')
    observed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(250), nullable=True)
