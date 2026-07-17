"""use Activity Audit Log as the only authentication event store

Revision ID: 20260717_auth_activity
Revises: 20260717_google_github_sso
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260717_auth_activity'
down_revision = '20260717_google_github_sso'
branch_labels = None
depends_on = None

OBSOLETE_PERMISSION_KEY = 'settings.view_login_activity'


def upgrade() -> None:
    # Anonymous failed sign-ins must be auditable even when no User row exists.
    op.alter_column(
        'notifications',
        'user_id',
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Development cutover: the unified Activity Audit Log is authoritative.
    # Existing legacy Login Activity rows are intentionally discarded.
    op.drop_table('auth_login_events')

    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text('SELECT id FROM permissions WHERE key = :key'),
        {'key': OBSOLETE_PERMISSION_KEY},
    ).scalar()
    if permission_id is not None:
        bind.execute(
            sa.text('DELETE FROM role_permissions WHERE permission_id = :permission_id'),
            {'permission_id': permission_id},
        )
        bind.execute(
            sa.text('DELETE FROM permissions WHERE id = :permission_id'),
            {'permission_id': permission_id},
        )


def downgrade() -> None:
    # Authentication rows may have a NULL user_id. Remove them before restoring
    # the previous non-null notification constraint.
    op.execute("DELETE FROM notifications WHERE event_type = 'authentication'")

    op.create_table(
        'auth_login_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auth_login_events_created_at'), 'auth_login_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_auth_login_events_reason'), 'auth_login_events', ['reason'], unique=False)
    op.create_index(op.f('ix_auth_login_events_source'), 'auth_login_events', ['source'], unique=False)
    op.create_index(op.f('ix_auth_login_events_success'), 'auth_login_events', ['success'], unique=False)
    op.create_index(op.f('ix_auth_login_events_user_id'), 'auth_login_events', ['user_id'], unique=False)
    op.create_index(op.f('ix_auth_login_events_username'), 'auth_login_events', ['username'], unique=False)

    op.alter_column(
        'notifications',
        'user_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
