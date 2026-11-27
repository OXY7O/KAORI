"""Separate OpenBao connection identity; never reinterpret Vault registrations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.security.credentials import EncryptedText


class OpenBaoInstance(db.Model):
    __tablename__ = 'openbao_instances'
    __table_args__ = (
        CheckConstraint("ownership IN ('internal', 'external')", name='ck_openbao_ownership'),
        CheckConstraint(
            "(ownership = 'internal' AND internal_slot = 'bundled') OR "
            "(ownership = 'external' AND internal_slot IS NULL)",
            name='ck_openbao_internal_slot',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False, unique=True
    )
    ownership: Mapped[str] = mapped_column(String(16), nullable=False)
    internal_slot: Mapped[str | None] = mapped_column(String(16), nullable=True, unique=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    cluster_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    auth_mount: Mapped[str] = mapped_column(String(160), nullable=False)
    role_id: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_id: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    detected_version: Mapped[str | None] = mapped_column(String(64))
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    integration_instance: Mapped[IntegrationInstance] = relationship('IntegrationInstance', lazy='joined')

    @property
    def name(self) -> str:
        return self.integration_instance.name

    @property
    def enabled(self) -> bool:
        return self.integration_instance.enabled
