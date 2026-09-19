from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.user import User


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    __table_args__ = (UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(
        db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    role: Mapped[Role] = relationship(
        'Role',
        back_populates='role_permissions',
        lazy='joined',
    )
    permission: Mapped[Permission] = relationship(
        'Permission',
        back_populates='role_permissions',
        lazy='joined',
    )


class Role(db.Model):
    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(80), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    role_permissions: Mapped[list[RolePermission]] = relationship(
        'RolePermission',
        back_populates='role',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
    permissions: Mapped[list[Permission]] = relationship(
        'Permission',
        secondary='role_permissions',
        viewonly=True,
        lazy='selectin',
    )
    users: Mapped[list[User]] = relationship(
        'User',
        back_populates='role_record',
        lazy='selectin',
    )

    def permission_keys(self) -> set[str]:
        return {permission.key for permission in self.permissions}


class Permission(db.Model):
    __tablename__ = 'permissions'

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False, index=True)
    module: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(db.String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    role_permissions: Mapped[list[RolePermission]] = relationship(
        'RolePermission',
        back_populates='permission',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
