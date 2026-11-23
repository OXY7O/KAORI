"""Provider-neutral existing Linux host identity for Infrastructure Automation (#5161).

This asset is a registered *intent*, not an SSH connection, remote host
attestation, or a Kubernetes node. Native NodeInventory remains API-owned.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class ComputeHostAsset(db.Model):
    """Stable KAORI asset key; integration attachment uses IntegrationBinding."""

    __tablename__ = 'compute_host_assets'
    __table_args__ = (
        UniqueConstraint('asset_key', name='uq_compute_host_asset_key'),
        UniqueConstraint(
            'site_key',
            'environment',
            'management_ipv4',
            name='uq_compute_host_site_environment_address',
        ),
        CheckConstraint('ssh_port BETWEEN 1 AND 65535', name='ck_compute_host_ssh_port'),
        CheckConstraint(
            "environment IN ('development', 'testing', 'staging', 'laboratory',"
            " 'sandbox', 'proof_of_concept', 'non_production')",
            name='ck_compute_host_non_production',
        ),
        Index('ix_compute_host_scope', 'site_key', 'environment', 'created_at'),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    asset_key: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    site_key: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    management_ipv4: Mapped[str] = mapped_column(String(45), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    registered_by_user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
