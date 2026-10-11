"""Capsule audit batch anti-replay + per-resource consent evidence schemas.

Dedicated staged proof tables, NOT the generic mutable AuditEvent journal.
No route, backend key material, INSERT service or executor is registered.
DDL guards are authored only in a separate Alembic revision and must not
be mistaken for applied database enforcement under the current gate HOLD.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions.db import db


class CapsuleHandoffAuditBatch(db.Model):
    __tablename__ = 'capsule_handoff_audit_batches'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(db.String(36), nullable=False)
    tenant_id: Mapped[str] = mapped_column(
        db.String(36), db.ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False,
    )
    cluster_id: Mapped[str] = mapped_column(db.String(36), nullable=False)
    generation: Mapped[int] = mapped_column(db.Integer, nullable=False)
    plan_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    worklist_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    resource_review_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    claims_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    receipt_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    collector_id: Mapped[str] = mapped_column(db.String(120), nullable=False)
    key_id: Mapped[str] = mapped_column(db.String(120), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False,
        server_default=db.text('CURRENT_TIMESTAMP'),
    )

    __table_args__ = (
        # Conservative once-only policy: never replace or replay one plan.
        db.UniqueConstraint('batch_id', name='uq_capsule_audit_batch_global_id'),
        db.UniqueConstraint('tenant_id', name='uq_capsule_audit_batch_tenant_once'),
        db.UniqueConstraint('tenant_id', 'plan_sha256', name='uq_capsule_audit_batch_plan_once'),
        db.UniqueConstraint(
            'batch_id', 'tenant_id', 'plan_sha256',
            'worklist_sha256', 'resource_review_sha256',
            name='uq_capsule_audit_batch_full_scope',
        ),
        db.CheckConstraint('generation > 0', name='ck_capsule_audit_batch_generation'),
        db.CheckConstraint(
            'length(batch_id) = 36 AND length(plan_sha256) = 64 '
            'AND length(worklist_sha256) = 64 '
            'AND length(resource_review_sha256) = 64 '
            'AND length(claims_sha256) = 64 '
            'AND length(receipt_sha256) = 64',
            name='ck_capsule_audit_batch_digest_shape',
        ),
    )


class CapsuleHandoffResourceConsentRecord(db.Model):
    __tablename__ = 'capsule_handoff_resource_consent_records'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        db.String(36), db.ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False,
    )
    batch_id: Mapped[str] = mapped_column(db.String(36), nullable=False)
    plan_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    worklist_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    resource_review_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    consent_manifest_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    resource_scope_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    target_count: Mapped[int] = mapped_column(db.Integer, nullable=False)
    requester_user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False,
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False,
    )
    successor_user_id: Mapped[int] = mapped_column(
        db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False,
    )
    accepted_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False,
        server_default=db.text('CURRENT_TIMESTAMP'),
    )

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['batch_id', 'tenant_id', 'plan_sha256',
             'worklist_sha256', 'resource_review_sha256'],
            ['capsule_handoff_audit_batches.batch_id',
             'capsule_handoff_audit_batches.tenant_id',
             'capsule_handoff_audit_batches.plan_sha256',
             'capsule_handoff_audit_batches.worklist_sha256',
             'capsule_handoff_audit_batches.resource_review_sha256'],
            ondelete='RESTRICT',
            name='fk_capsule_resource_consent_exact_audit_batch',
        ),
        db.UniqueConstraint('tenant_id', 'plan_sha256', name='uq_capsule_resource_consent_plan_once'),
        db.UniqueConstraint('tenant_id', 'consent_manifest_sha256', name='uq_capsule_resource_consent_manifest'),
        db.CheckConstraint(
            'target_count BETWEEN 1 AND 330',
            name='ck_capsule_resource_consent_target_count',
        ),
        db.CheckConstraint(
            'requester_user_id <> reviewer_user_id '
            'AND requester_user_id <> successor_user_id '
            'AND reviewer_user_id <> successor_user_id',
            name='ck_capsule_resource_consent_independent_actors',
        ),
        db.CheckConstraint(
            'length(batch_id) = 36 AND length(plan_sha256) = 64 '
            'AND length(worklist_sha256) = 64 '
            'AND length(resource_review_sha256) = 64 '
            'AND length(consent_manifest_sha256) = 64 '
            'AND length(resource_scope_sha256) = 64',
            name='ck_capsule_resource_consent_digest_shape',
        ),
    )
