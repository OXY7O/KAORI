"""add auth login events

Revision ID: 20260704_add_auth_login_events
Revises: 195a5f19967b
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260704_add_auth_login_events'
down_revision = '195a5f19967b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'auth_login_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column(
            'source',
            sa.String(length=50),
            nullable=False,
            server_default='database',
        ),
        sa.Column(
            'success',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_auth_login_events_created_at'),
        'auth_login_events',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_auth_login_events_reason'),
        'auth_login_events',
        ['reason'],
        unique=False,
    )
    op.create_index(
        op.f('ix_auth_login_events_source'),
        'auth_login_events',
        ['source'],
        unique=False,
    )
    op.create_index(
        op.f('ix_auth_login_events_success'),
        'auth_login_events',
        ['success'],
        unique=False,
    )
    op.create_index(
        op.f('ix_auth_login_events_user_id'),
        'auth_login_events',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_auth_login_events_username'),
        'auth_login_events',
        ['username'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_auth_login_events_username'), table_name='auth_login_events')
    op.drop_index(op.f('ix_auth_login_events_user_id'), table_name='auth_login_events')
    op.drop_index(op.f('ix_auth_login_events_success'), table_name='auth_login_events')
    op.drop_index(op.f('ix_auth_login_events_source'), table_name='auth_login_events')
    op.drop_index(op.f('ix_auth_login_events_reason'), table_name='auth_login_events')
    op.drop_index(op.f('ix_auth_login_events_created_at'), table_name='auth_login_events')
    op.drop_table('auth_login_events')
