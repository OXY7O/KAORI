from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.rbac.defaults import DEFAULT_ROLE_PERMISSIONS

if TYPE_CHECKING:
    from app.models.rbac import Role


# User model for authentication and user management.
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    __table_args__ = (
        db.Index(
            'uq_users_username_active',
            'username',
            unique=True,
            postgresql_where=db.text('deleted_at IS NULL'),
        ),
        db.Index(
            'uq_users_email_active',
            'email',
            unique=True,
            postgresql_where=db.text('deleted_at IS NULL'),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(db.String(100), nullable=False)

    email: Mapped[str] = mapped_column(db.String(255), nullable=False)

    display_name: Mapped[str | None] = mapped_column(db.String(150), nullable=True)

    timezone: Mapped[str] = mapped_column(db.String(100), default='UTC', nullable=False)

    timezone_mode: Mapped[str] = mapped_column(db.String(20), default='manual', nullable=False)

    locale: Mapped[str] = mapped_column(db.String(20), default='en-US', nullable=False)

    date_format: Mapped[str] = mapped_column(db.String(30), default='day_month_year', nullable=False)

    time_format: Mapped[str] = mapped_column(db.String(10), default='24h', nullable=False)

    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False, default='')

    role_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('roles.id', ondelete='SET NULL'), nullable=True, index=True
    )

    auth_source: Mapped[str] = mapped_column(db.String(50), default='database', nullable=False, index=True)

    external_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)

    account_is_active: Mapped[bool] = mapped_column('is_active', db.Boolean, default=True, nullable=False, index=True)

    is_super_admin: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    last_login_ip: Mapped[str | None] = mapped_column(db.String(100), nullable=True)

    last_auth_source: Mapped[str | None] = mapped_column(db.String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)

    external_identities = relationship(
        'ExternalIdentityLink',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='selectin',
    )

    role_record: Mapped[Role | None] = relationship(
        'Role',
        back_populates='users',
        lazy='joined',
    )

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.account_is_active and self.deleted_at is None)

    @property
    def display_label(self) -> str:
        display_name = (self.display_name or '').strip()
        if display_name:
            return display_name

        return self.username

    @property
    def has_display_name(self) -> bool:
        return bool((self.display_name or '').strip())

    @property
    def role_name(self) -> str:
        if self.role_record is not None:
            return self.role_record.name
        return 'viewer'

    @property
    def role_display_name(self) -> str:
        if self.role_record is not None:
            return self.role_record.display_name
        return self.role_name.replace('_', ' ').title()

    @property
    def is_external(self) -> bool:
        return self.auth_source != 'database'

    @property
    def is_admin_level(self) -> bool:
        return bool(self.is_super_admin or self.role_name == 'admin')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission_key: str) -> bool:
        if self.is_super_admin:
            return True

        # A persisted role assignment is authoritative. An inactive role must
        # revoke access instead of falling through to the code-owned default
        # permission map for a role with the same slug.
        if self.role_record is not None:
            if not self.role_record.is_active:
                return False
            return permission_key in self.role_record.permission_keys()

        # Compatibility fallback for legacy/bootstrap records that have not yet
        # been attached to a persisted role. Keep this path isolated from normal
        # role lifecycle enforcement.
        return permission_key in DEFAULT_ROLE_PERMISSIONS.get(self.role_name, set())
