"""Storage-only, provider-neutral scoped authorization policy evidence.

Architecture #724 / implementation child #2723. This module does not
evaluate/grant/approve resource access; policy creation and activation must
remain unavailable until #2724/#2725 are admitted. No Secret values or
Vault credential material belongs to these models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


class ScopeAccessPolicy(db.Model):
    """Immutable policy target/subject identity with a revision pointer."""

    __tablename__ = 'access_scope_policies'
    __table_args__ = (
        CheckConstraint(
            "scope_level IN ('instance', 'vault_mount', 'automation_credential')",
            name='ck_access_scope_policy_level',
        ),
        CheckConstraint(
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            " OR ((scope_level = 'vault_mount' OR scope_level = 'automation_credential')"
            " AND provider_namespace IS NOT NULL"
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
            name='ck_access_scope_policy_exact_target',
        ),
        CheckConstraint(
            "(scope_level = 'automation_credential' AND permission_key = 'secrets_pki.use_automation_credential')"
            " OR (scope_level <> 'automation_credential' AND permission_key <> 'secrets_pki.use_automation_credential')",
            name='ck_access_scope_policy_credential_permission',
        ),
        CheckConstraint(
            'current_revision > 0',
            name='ck_access_scope_policy_revision',
        ),
        Index(
            'ix_access_scope_policy_principal_target',
            'principal_user_id',
            'permission_key',
            'integration_instance_id',
            'scope_level',
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    principal_user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
    )
    permission_key: Mapped[str] = mapped_column(
        String(120),
        ForeignKey('permissions.key', ondelete='RESTRICT'),
        nullable=False,
    )
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'),
        nullable=False,
    )
    scope_level: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_namespace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mount: Mapped[str | None] = mapped_column(String(160), nullable=True)
    current_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    revisions: Mapped[list[ScopeAccessPolicyRevision]] = relationship(
        'ScopeAccessPolicyRevision',
        back_populates='policy',
        order_by='ScopeAccessPolicyRevision.revision_number',
        lazy='selectin',
    )


class ScopeAccessPolicyRevision(db.Model):
    """Append-only intended review record; only #2724 may implement writes.

    A revision is not an authorization decision. Approval and mandatory audit
    evidence must be committed before a later evaluator can qualify access.
    """

    __tablename__ = 'access_scope_policy_revisions'
    __table_args__ = (
        UniqueConstraint(
            'policy_id',
            'revision_number',
            name='uq_access_scope_policy_revision',
        ),
        CheckConstraint(
            "lifecycle_status IN ('draft', 'active', 'suspended', 'revoked', 'expired', 'withdrawn')",
            name='ck_access_scope_revision_state',
        ),
        CheckConstraint(
            'revision_number > 0',
            name='ck_access_scope_revision_number',
        ),
        CheckConstraint(
            'effective_until > effective_from',
            name='ck_access_scope_revision_window',
        ),
        CheckConstraint(
            "lifecycle_status <> 'active' OR"
            ' (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL'
            ' AND approved_by_user_id <> requested_by_user_id)',
            name='ck_access_scope_revision_approved',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('access_scope_policies.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default='draft',
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    effective_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    change_reason: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    policy: Mapped[ScopeAccessPolicy] = relationship(
        'ScopeAccessPolicy',
        back_populates='revisions',
    )


class AutomationCredentialScopeTarget(db.Model):
    """Exact immutable selector owned by one canonical policy; never a permit."""

    __tablename__ = 'access_automation_credential_targets'
    __table_args__ = (
        CheckConstraint('secret_version > 0', name='ck_access_auto_credential_version'),
        CheckConstraint('length(host_revision) = 64', name='ck_access_auto_credential_host_revision'),
        CheckConstraint('length(reference_fingerprint) = 64', name='ck_access_auto_credential_reference'),
        CheckConstraint('length(source_revision) = 40', name='ck_access_auto_credential_source'),
        CheckConstraint(
            "profile_key <> '' AND profile_key NOT LIKE '%*%' AND operation_key <> '' AND operation_key NOT LIKE '%*%'",
            name='ck_access_auto_credential_operation',
        ),
    )

    policy_id: Mapped[str] = mapped_column(
        ForeignKey('access_scope_policies.id', ondelete='RESTRICT'), primary_key=True
    )
    ansible_connection_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey('automation_inventory_assignments.id', ondelete='RESTRICT'), nullable=False
    )
    host_id: Mapped[str] = mapped_column(
        ForeignKey('automation_host_assets.id', ondelete='RESTRICT'), nullable=False
    )
    host_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_identity_id: Mapped[str] = mapped_column(
        ForeignKey('secrets_pki_secret_identities.id', ondelete='RESTRICT'), nullable=False
    )
    secret_representation_id: Mapped[int] = mapped_column(
        ForeignKey('secrets_pki_secret_representations.id', ondelete='RESTRICT'), nullable=False
    )
    secret_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_revision: Mapped[str] = mapped_column(String(40), nullable=False)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(120), nullable=False)
