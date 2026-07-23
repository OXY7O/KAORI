from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class IntelligenceDecision(db.Model):
    """Immutable persisted decision snapshot and its workflow state."""

    __tablename__ = 'intelligence_decisions'
    __table_args__ = (
        CheckConstraint(
            "policy_outcome IN ('allowed', 'needs_approval', 'blocked')",
            name='ck_intelligence_decisions_policy_outcome',
        ),
        CheckConstraint(
            "workflow_status IN ('ready', 'pending_approval', 'approved', 'rejected', 'expired', 'dispatched')",
            name='ck_intelligence_decisions_workflow_status',
        ),
        Index('ix_intelligence_decisions_status_created', 'workflow_status', 'created_at'),
        Index('ix_intelligence_decisions_cluster_status', 'cluster_id', 'workflow_status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        db.String(64), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    recommendation_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(db.String(80), nullable=False)
    knowledge_version: Mapped[str | None] = mapped_column(db.String(120), nullable=True)
    action_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    cluster_id: Mapped[str | None] = mapped_column(db.String(80), nullable=True, index=True)
    namespace: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(db.String(30), nullable=False, index=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(db.String(64), nullable=False, index=True)
    inventory_generation: Mapped[str | None] = mapped_column(db.String(80), nullable=True)
    alert_fingerprint: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    policy_outcome: Mapped[str] = mapped_column(db.String(30), nullable=False, index=True)
    policy_reason: Mapped[str] = mapped_column(db.String(500), nullable=False)
    approval_required: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    workflow_status: Mapped[str] = mapped_column(db.String(30), nullable=False, index=True)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
    approvals: Mapped[list[IntelligenceDecisionApproval]] = relationship(
        'IntelligenceDecisionApproval', back_populates='decision', cascade='all, delete-orphan',
        passive_deletes=True
    )
    executions: Mapped[list[IntelligenceExecutionJournal]] = relationship(
        'IntelligenceExecutionJournal', back_populates='decision', cascade='all, delete-orphan',
        passive_deletes=True
    )


class IntelligenceDecisionApproval(db.Model):
    """Append-only approval or rejection evidence for a decision."""

    __tablename__ = 'intelligence_decision_approvals'
    __table_args__ = (
        CheckConstraint("outcome IN ('approved', 'rejected')", name='ck_decision_approval_outcome'),
        UniqueConstraint('decision_id', name='uq_active_decision_approval'),
        Index('ix_decision_approvals_actor_created', 'actor_user_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(
        db.ForeignKey('intelligence_decisions.id', ondelete='CASCADE'), nullable=False, index=True
    )
    outcome: Mapped[str] = mapped_column(db.String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(db.String(1000), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    evidence_hash: Mapped[str] = mapped_column(db.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    decision: Mapped[IntelligenceDecision] = relationship('IntelligenceDecision', back_populates='approvals')
    actor: Mapped[User | None] = relationship('User', foreign_keys=[actor_user_id])


class IntelligenceExecutionJournal(db.Model):
    """One-time token issuance and dispatch lifecycle for resolver execution."""

    __tablename__ = 'intelligence_execution_journal'
    __table_args__ = (
        CheckConstraint(
            "status IN ('authorized', 'dispatched', 'succeeded', 'failed', 'canceled')",
            name='ck_intelligence_execution_status',
        ),
        UniqueConstraint('token_nonce_hash', name='uq_intelligence_execution_nonce'),
        Index('ix_intelligence_execution_decision_status', 'decision_id', 'status'),
        Index('ix_intelligence_execution_created', 'created_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        db.String(64), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    decision_id: Mapped[int] = mapped_column(
        db.ForeignKey('intelligence_decisions.id', ondelete='CASCADE'), nullable=False, index=True
    )
    token_nonce_hash: Mapped[str] = mapped_column(db.String(64), nullable=False)
    action_key: Mapped[str] = mapped_column(db.String(255), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(db.String(64), nullable=False)
    status: Mapped[str] = mapped_column(db.String(30), nullable=False, default='authorized', index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    resolver_job_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('job_executions.id', ondelete='SET NULL'), nullable=True, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    decision: Mapped[IntelligenceDecision] = relationship('IntelligenceDecision', back_populates='executions')
    requested_by: Mapped[User | None] = relationship('User', foreign_keys=[requested_by_user_id])
