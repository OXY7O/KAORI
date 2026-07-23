"""resolver operational controls and observability

Revision ID: 20260723_resolver_controls
Revises: 20260723_resolver_registry
"""
from alembic import op
import sqlalchemy as sa

revision = '20260723_resolver_controls'
down_revision = '20260723_resolver_registry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'resolver_operational_controls',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cluster_id', sa.String(length=36), nullable=True),
        sa.Column('global_kill_switch', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('maintenance_mode', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('concurrency_limit', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('circuit_failure_threshold', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('circuit_cooldown_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('circuit_open_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('concurrency_limit >= 1', name='ck_resolver_control_concurrency'),
        sa.CheckConstraint('rate_limit_per_minute >= 1', name='ck_resolver_control_rate'),
        sa.CheckConstraint('circuit_failure_threshold >= 1', name='ck_resolver_control_threshold'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_resolver_operational_controls_cluster_id', 'resolver_operational_controls', ['cluster_id'])
    op.execute(
        "CREATE UNIQUE INDEX uq_resolver_operational_control_scope "
        "ON resolver_operational_controls (COALESCE(cluster_id, '__global__'))"
    )


def downgrade() -> None:
    op.drop_table('resolver_operational_controls')
