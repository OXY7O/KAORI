"""mvp2 user management rbac

Revision ID: 20260704_0900
Revises: 20260704_user_login_meta
Create Date: 2026-07-04 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260704_0900'
down_revision = '20260704_user_login_meta'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('display_name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=False)

    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=120), nullable=False),
        sa.Column('module', sa.String(length=80), nullable=False),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index(op.f('ix_permissions_key'), 'permissions', ['key'], unique=False)
    op.create_index(op.f('ix_permissions_module'), 'permissions', ['module'], unique=False)

    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )
    op.create_index(op.f('ix_role_permissions_permission_id'), 'role_permissions', ['permission_id'], unique=False)
    op.create_index(op.f('ix_role_permissions_role_id'), 'role_permissions', ['role_id'], unique=False)

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('role_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('external_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('is_super_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key('fk_users_role_id_roles', 'roles', ['role_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('ix_users_role_id', ['role_id'])
        batch_op.create_index('ix_users_external_id', ['external_id'])
        batch_op.create_index('ix_users_is_active', ['is_active'])
        batch_op.create_index('ix_users_deleted_at', ['deleted_at'])
        batch_op.create_index('ix_users_auth_source', ['auth_source'])

    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('target_type', sa.String(length=80), nullable=False),
        sa.Column('target_id', sa.String(length=120), nullable=True),
        sa.Column('action', sa.String(length=120), nullable=False),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_events_actor_user_id'), 'audit_events', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_events_target_id'), 'audit_events', ['target_id'], unique=False)
    op.create_index(op.f('ix_audit_events_target_type'), 'audit_events', ['target_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_events_target_type'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_target_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_created_at'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_actor_user_id'), table_name='audit_events')
    op.drop_table('audit_events')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index('ix_users_auth_source')
        batch_op.drop_index('ix_users_deleted_at')
        batch_op.drop_index('ix_users_is_active')
        batch_op.drop_index('ix_users_external_id')
        batch_op.drop_index('ix_users_role_id')
        batch_op.drop_constraint('fk_users_role_id_roles', type_='foreignkey')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('is_super_admin')
        batch_op.drop_column('is_active')
        batch_op.drop_column('external_id')
        batch_op.drop_column('role_id')
        batch_op.drop_column('display_name')

    op.drop_index(op.f('ix_role_permissions_role_id'), table_name='role_permissions')
    op.drop_index(op.f('ix_role_permissions_permission_id'), table_name='role_permissions')
    op.drop_table('role_permissions')
    op.drop_index(op.f('ix_permissions_module'), table_name='permissions')
    op.drop_index(op.f('ix_permissions_key'), table_name='permissions')
    op.drop_table('permissions')
    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_table('roles')
