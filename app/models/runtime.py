from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class IntegrationRuntimeObservation(db.Model):
    __tablename__ = 'integration_runtime_observations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='SET NULL'), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(120), nullable=False)
    instance_name: Mapped[str] = mapped_column(String(180), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False, default='manual')
    readiness: Mapped[str] = mapped_column(String(40), nullable=False)
    health_status: Mapped[str] = mapped_column(String(40), nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compatibility_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capability_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capability_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    diagnostics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    __table_args__ = (
        Index('ix_integration_runtime_canonical_instance', 'integration_instance_id', 'observed_at'),
        Index('ix_integration_runtime_provider_instance', 'provider', 'instance_id', 'observed_at'),
        Index('ix_integration_runtime_health', 'provider', 'health_status', 'observed_at'),
    )
