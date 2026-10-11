"""Capsule-specific write-once event ledger schema (#1229).

A dedicated SQL table, not the generic mutable AuditEvent journal.
No service writes it until provider handoff admission is independently approved.
Database trigger protections are authored in the paired Alembic migration.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class CapsuleHandoffLedgerEvent(db.Model):
    __tablename__ = 'capsule_handoff_ledger_events'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        db.String(36), db.ForeignKey('tenants.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    cluster_id: Mapped[str] = mapped_column(db.String(36), nullable=False)
    generation: Mapped[int] = mapped_column(db.Integer, nullable=False)
    plan_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    handoff_fingerprint: Mapped[str] = mapped_column(db.String(64), nullable=False)
    worklist_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    attempt_id: Mapped[str] = mapped_column(db.String(36), nullable=False)
    sequence: Mapped[int] = mapped_column(db.Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(db.String(32), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False,
    )
    event_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    previous_event_sha256: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    event_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    event_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False,
        server_default=db.text('CURRENT_TIMESTAMP'),
    )

    __table_args__ = (
        # A Tenant has one irreversible attempt history. A future independently
        # governed reset requires a separately reviewed schema/workflow.
        db.UniqueConstraint('tenant_id', 'sequence', name='uq_capsule_ledger_tenant_sequence'),
        db.UniqueConstraint('tenant_id', 'attempt_id', 'sequence', name='uq_capsule_ledger_attempt_sequence'),
        db.UniqueConstraint('tenant_id', 'event_sha256', name='uq_capsule_ledger_tenant_digest'),
        db.CheckConstraint('generation > 0', name='ck_capsule_ledger_generation'),
        db.CheckConstraint(
            'length(plan_sha256) = 64 AND length(handoff_fingerprint) = 64 '
            'AND length(worklist_sha256) = 64 AND length(event_sha256) = 64 '
            'AND (previous_event_sha256 IS NULL OR length(previous_event_sha256) = 64) '
            'AND length(attempt_id) = 36',
            name='ck_capsule_ledger_bound_reference_lengths',
        ),
        db.CheckConstraint(
            "(sequence = 1 AND event_type = 'started') OR "
            "(sequence = 2 AND event_type IN ('partial', 'readback_candidate')) OR "
            "(sequence = 3 AND event_type = 'recovery_reviewed')",
            name='ck_capsule_ledger_event_progression',
        ),
        db.CheckConstraint('sequence BETWEEN 1 AND 3', name='ck_capsule_ledger_sequence'),
    )
