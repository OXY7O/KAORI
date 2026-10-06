"""add automatic Kubernetes inventory sync policy

Revision ID: 20260724_inventory_sync
Revises: 20260723_resolver_readiness
"""

from alembic import op
import sqlalchemy as sa

revision = '20260724_inventory_sync'
down_revision = '20260723_resolver_readiness'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'inventory_sync_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('interval_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('id = 1', name='ck_inventory_sync_policy_singleton'),
        sa.CheckConstraint(
            'interval_minutes >= 5 AND interval_minutes <= 1440',
            name='ck_inventory_sync_policy_interval',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute(
        'INSERT INTO inventory_sync_policies '
        '(id, enabled, interval_minutes, next_run_at, updated_at) '
        "VALUES (1, TRUE, 60, CURRENT_TIMESTAMP + INTERVAL '60 minutes', CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.drop_table('inventory_sync_policies')
