from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class SecretRevealNamespacePolicy(db.Model):
    __tablename__ = 'secret_reveal_namespace_policies'
    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'namespace',
            name='uq_secret_reveal_namespace_policy_cluster_namespace',
        ),
    )

    id: Mapped[str] = mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    cluster_id: Mapped[str] = mapped_column(
        db.ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    namespace: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
        index=True,
    )
    policy: Mapped[str] = mapped_column(
        db.String(32),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    cluster = relationship('Cluster', lazy='joined')
    created_by = relationship('User', foreign_keys=[created_by_user_id], lazy='joined')
    updated_by = relationship('User', foreign_keys=[updated_by_user_id], lazy='joined')


class SecretRevealRequest(db.Model):
    __tablename__ = 'secret_reveal_requests'

    id: Mapped[str] = mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    configuration_inventory_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('configuration_inventory.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    cluster_id: Mapped[str] = mapped_column(
        db.ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    namespace: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    secret_name: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    secret_type: Mapped[str] = mapped_column(db.String(255), nullable=False)
    key_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    policy: Mapped[str] = mapped_column(db.String(32), nullable=False)
    reason: Mapped[str] = mapped_column(db.Text(), nullable=False)
    ticket_reference: Mapped[str] = mapped_column(db.String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        db.String(24),
        nullable=False,
        default='pending',
        index=True,
    )
    requester_user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    approver_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    requester_ip: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    revealed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    requester = relationship('User', foreign_keys=[requester_user_id], lazy='joined')
    approver = relationship('User', foreign_keys=[approver_user_id], lazy='joined')
    cluster = relationship('Cluster', lazy='joined')
    inventory = relationship('ConfigurationInventory', lazy='joined')
