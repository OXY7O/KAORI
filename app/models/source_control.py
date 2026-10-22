"""Source Control persisted native identities; GitHub remains the source authority.

#559 and SC-01 #2740. These tables hold source identities and grant
relationships, NOT Git repositories, code, App private keys, or OAuth tokens.
The IntegrationInstance remains the canonical connection lifecycle record.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SourceAccount(db.Model):
    """Provider-native organization/user identity independent of an App grant."""

    __tablename__ = 'source_control_accounts'
    __table_args__ = (
        UniqueConstraint('provider_key', 'host_key', 'native_account_id', name='uq_sc_account_native'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, default='github')
    host_key: Mapped[str] = mapped_column(String(255), nullable=False)
    native_account_id: Mapped[str] = mapped_column(String(80), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class SourceInstallation(db.Model):
    """One canonical IntegrationInstance connects to one explicit App grant."""

    __tablename__ = 'source_control_installations'
    __table_args__ = (
        UniqueConstraint('integration_instance_id', name='uq_sc_installation_connection'),
        UniqueConstraint(
            'provider_key', 'host_key', 'native_app_id', 'native_installation_id',
            name='uq_sc_installation_native',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_instance_id: Mapped[int] = mapped_column(
        ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, default='github')
    host_key: Mapped[str] = mapped_column(String(255), nullable=False)
    native_app_id: Mapped[str] = mapped_column(String(80), nullable=False)
    native_installation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey('source_control_accounts.id', ondelete='RESTRICT'), nullable=True
    )
    repository_scope: Mapped[str] = mapped_column(String(16), nullable=False, default='unknown')
    grant_status: Mapped[str] = mapped_column(String(30), nullable=False, default='unknown')
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    account: Mapped[SourceAccount | None] = relationship('SourceAccount')
    grants: Mapped[list[SourceRepositoryGrant]] = relationship(
        'SourceRepositoryGrant', back_populates='installation',
        order_by='SourceRepositoryGrant.valid_from.desc()',
    )


class SourceRepository(db.Model):
    """Repository native ID survives an evidenced owner/name rename or transfer."""

    __tablename__ = 'source_control_repositories'
    __table_args__ = (
        UniqueConstraint('provider_key', 'host_key', 'native_repository_id', name='uq_sc_repository_native'),
        Index('ix_sc_repository_account', 'account_id', 'last_observed_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, default='github')
    host_key: Mapped[str] = mapped_column(String(255), nullable=False)
    native_repository_id: Mapped[str] = mapped_column(String(80), nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey('source_control_accounts.id', ondelete='RESTRICT'), nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(600), nullable=True)
    archived: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    provider_presence: Mapped[str] = mapped_column(String(30), nullable=False, default='unknown')
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    account: Mapped[SourceAccount | None] = relationship('SourceAccount')


class SourceRepositoryGrant(db.Model):
    """Effective-dated installation access. Access loss is not repository deletion."""

    __tablename__ = 'source_control_repository_grants'
    __table_args__ = (
        UniqueConstraint('installation_id', 'repository_id', 'valid_from', name='uq_sc_grant_transition'),
        CheckConstraint(
            'valid_until IS NULL OR valid_until > valid_from', name='ck_sc_grant_valid_window'
        ),
        Index(
            'uq_sc_grant_current', 'installation_id', 'repository_id', unique=True,
            postgresql_where=text('valid_until IS NULL'),
            sqlite_where=text('valid_until IS NULL'),
        ),
        Index('ix_sc_grant_repository_history', 'repository_id', 'valid_from'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_id: Mapped[int] = mapped_column(
        ForeignKey('source_control_installations.id', ondelete='RESTRICT'), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey('source_control_repositories.id', ondelete='RESTRICT'), nullable=False
    )
    access_status: Mapped[str] = mapped_column(String(30), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    installation: Mapped[SourceInstallation] = relationship(
        'SourceInstallation', back_populates='grants'
    )
    repository: Mapped[SourceRepository] = relationship('SourceRepository')


class SourceRevision(db.Model):
    """Sparse exact commit identity, scoped to its canonical repository."""

    __tablename__ = 'source_control_revisions'
    __table_args__ = (
        UniqueConstraint('repository_id', 'commit_sha', name='uq_sc_revision_repo_sha'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey('source_control_repositories.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(128), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    repository: Mapped[SourceRepository] = relationship('SourceRepository')


class SourceReference(db.Model):
    """Current branch/tag pointer, with separately preserved observed transitions."""

    __tablename__ = 'source_control_references'
    __table_args__ = (
        UniqueConstraint('repository_id', 'full_ref', name='uq_sc_ref_repo_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey('source_control_repositories.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    full_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    current_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey('source_control_revisions.id', ondelete='RESTRICT'), nullable=True
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, default='unknown')
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    repository: Mapped[SourceRepository] = relationship('SourceRepository')
    current_revision: Mapped[SourceRevision | None] = relationship('SourceRevision')


class SourceReferenceTransition(db.Model):
    """Observation history; a ref movement is never a new source revision."""

    __tablename__ = 'source_control_reference_transitions'
    __table_args__ = (
        UniqueConstraint('reference_id', 'observed_at', name='uq_sc_ref_transition_observation'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference_id: Mapped[int] = mapped_column(
        ForeignKey('source_control_references.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    target_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey('source_control_revisions.id', ondelete='RESTRICT'), nullable=True
    )
    transition_state: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reference: Mapped[SourceReference] = relationship('SourceReference')
    target_revision: Mapped[SourceRevision | None] = relationship('SourceRevision')
