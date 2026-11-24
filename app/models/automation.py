"""KAORI-owned pre-provision Linux host identity and inventory assignment (#5161).

Distinct from observed Kubernetes NodeInventory, Ansible-native inventories,
provider connection configuration, SSH credentials, and execution evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AutomationHostAsset(db.Model):
    """KAORI canonical Linux host asset for existing VM/bare-metal intent."""

    __tablename__ = 'automation_host_assets'
    __table_args__ = (
        UniqueConstraint('environment', 'address', name='uq_automation_host_env_ip'),
        UniqueConstraint('environment', 'name', name='uq_automation_host_env_name'),
        Index('ix_automation_host_scope', 'environment', 'lifecycle_status'),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    address: Mapped[str] = mapped_column(String(45), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default='registered')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    assignments: Mapped[list[AutomationInventoryAssignment]] = relationship(
        'AutomationInventoryAssignment', back_populates='host', passive_deletes=True
    )


class AutomationInventoryAssignment(db.Model):
    """Explicit Ansible instance → existing-host role intent; no execution trust."""

    __tablename__ = 'automation_inventory_assignments'
    __table_args__ = (
        UniqueConstraint('integration_instance_id', 'host_id', name='uq_automation_assignment_instance_host'),
        Index('ix_automation_assignment_instance', 'integration_instance_id', 'enabled'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False
    )
    host_id: Mapped[str] = mapped_column(ForeignKey('automation_host_assets.id', ondelete='RESTRICT'), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    host: Mapped[AutomationHostAsset] = relationship('AutomationHostAsset', back_populates='assignments')


class AutomationHostAccessBinding(db.Model):
    """Reference-only selection for one inventory membership, never a trust grant."""

    __tablename__ = 'automation_host_access_bindings'
    __table_args__ = (
        CheckConstraint('secret_version > 0', name='ck_auto_host_access_version'),
        CheckConstraint('length(host_revision) = 64', name='ck_auto_host_access_revision'),
        CheckConstraint('length(reference_fingerprint) = 64', name='ck_auto_host_access_fingerprint'),
        CheckConstraint('length(host_key_digest) = 71', name='ck_auto_host_access_key_digest'),
    )

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey('automation_inventory_assignments.id', ondelete='RESTRICT'), primary_key=True
    )
    secret_representation_id: Mapped[int] = mapped_column(
        ForeignKey('secrets_pki_secret_representations.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    secret_version: Mapped[int] = mapped_column(Integer, nullable=False)
    host_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    host_key_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
