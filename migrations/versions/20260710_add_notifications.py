"""add operational notifications

Revision ID: 20260710_notifications
Revises: 20260707_tls_governance
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260710_notifications'
down_revision: Union[str, None] = '20260707_tls_governance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('message', sa.String(length=255), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('action_url', sa.String(length=500), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        op.f('ix_notifications_user_id'),
        'notifications',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_notifications_event_type'),
        'notifications',
        ['event_type'],
        unique=False,
    )
    op.create_index(
        op.f('ix_notifications_status'),
        'notifications',
        ['status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_notifications_created_at'),
        'notifications',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_notifications_read_at'),
        'notifications',
        ['read_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_notifications_read_at'),
        table_name='notifications',
    )
    op.drop_index(
        op.f('ix_notifications_created_at'),
        table_name='notifications',
    )
    op.drop_index(
        op.f('ix_notifications_status'),
        table_name='notifications',
    )
    op.drop_index(
        op.f('ix_notifications_event_type'),
        table_name='notifications',
    )
    op.drop_index(
        op.f('ix_notifications_user_id'),
        table_name='notifications',
    )
    op.drop_table('notifications')
