from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.user import User


class KnowledgeRunbook(db.Model):
    """Stable runbook identity; executable content lives in immutable revisions."""

    __tablename__ = 'knowledge_runbooks'
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('active', 'deprecated', 'archived')", name='ck_knowledge_runbook_lifecycle'
        ),
        Index('ix_knowledge_runbooks_status_updated', 'lifecycle_status', 'updated_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(db.String(64), nullable=False, unique=True, default=lambda: str(uuid4()))
    runbook_key: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(db.String(30), nullable=False, default='active', index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
    revisions: Mapped[list[KnowledgeRunbookRevision]] = relationship(
        'KnowledgeRunbookRevision', back_populates='runbook', cascade='all, delete-orphan', passive_deletes=True
    )


class KnowledgeRunbookRevision(db.Model):
    """Versioned runbook content. Published revisions are immutable by service contract."""

    __tablename__ = 'knowledge_runbook_revisions'
    __table_args__ = (
        CheckConstraint(
            "publication_status IN ('draft', 'published', 'withdrawn')", name='ck_runbook_revision_publication'
        ),
        CheckConstraint(
            "approval_policy IN ('allowed', 'needs_approval', 'blocked')", name='ck_runbook_revision_approval_policy'
        ),
        UniqueConstraint('runbook_id', 'version', name='uq_runbook_revision_version'),
        UniqueConstraint('content_hash', name='uq_runbook_revision_content_hash'),
        Index('ix_runbook_revisions_runbook_status', 'runbook_id', 'publication_status'),
        Index('ix_runbook_revisions_action_status', 'action_key', 'publication_status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(db.String(64), nullable=False, unique=True, default=lambda: str(uuid4()))
    runbook_id: Mapped[int] = mapped_column(
        db.ForeignKey('knowledge_runbooks.id', ondelete='CASCADE'), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(db.String(80), nullable=False)
    publication_status: Mapped[str] = mapped_column(db.String(30), nullable=False, default='draft', index=True)
    action_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    resolver_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    approval_policy: Mapped[str] = mapped_column(db.String(30), nullable=False, default='needs_approval')
    required_evidence_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    required_capabilities_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    compatibility_profiles_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    change_level: Mapped[str] = mapped_column(db.String(20), nullable=False, default='patch')
    parameter_schema_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(db.JSON, nullable=False, default=list)
    rollback_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    content_hash: Mapped[str] = mapped_column(db.String(64), nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    published_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    published_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    publication_validation_json: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    runbook: Mapped[KnowledgeRunbook] = relationship('KnowledgeRunbook', back_populates='revisions')
    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
    published_by: Mapped[User | None] = relationship('User', foreign_keys=[published_by_user_id])
    reviewed_by: Mapped[User | None] = relationship('User', foreign_keys=[reviewed_by_user_id])


class KnowledgeRunbookAlertBinding(db.Model):
    """Deterministic alert/rule selector bound to a published runbook revision."""

    __tablename__ = 'knowledge_runbook_alert_bindings'
    __table_args__ = (
        CheckConstraint("lifecycle_status IN ('active', 'disabled')", name='ck_runbook_alert_binding_lifecycle'),
        UniqueConstraint('binding_key', name='uq_runbook_alert_binding_key'),
        Index('ix_runbook_alert_binding_rule_active', 'rule_key', 'lifecycle_status'),
        Index('ix_runbook_alert_binding_alert_active', 'alertname', 'lifecycle_status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(db.String(64), nullable=False, unique=True, default=lambda: str(uuid4()))
    binding_key: Mapped[str] = mapped_column(db.String(255), nullable=False)
    runbook_revision_id: Mapped[int] = mapped_column(
        db.ForeignKey('knowledge_runbook_revisions.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    rule_key: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    alertname: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    cluster_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    namespace: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    required_labels_json: Mapped[dict[str, str]] = mapped_column(db.JSON, nullable=False, default=dict)
    evidence_mapping_json: Mapped[dict[str, str]] = mapped_column(db.JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    lifecycle_status: Mapped[str] = mapped_column(db.String(20), nullable=False, default='active', index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    revision: Mapped[KnowledgeRunbookRevision] = relationship('KnowledgeRunbookRevision')
    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
