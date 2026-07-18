"""add prometheus runtime capability state

Revision ID: 20260718_prom_runtime
Revises: 20260718_integration_runtime
"""
from alembic import op
import sqlalchemy as sa

revision = '20260718_prom_runtime'
down_revision = '20260718_integration_runtime'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('prometheus_configs', sa.Column('capability_profile', sa.String(100), nullable=True))
    op.add_column('prometheus_configs', sa.Column('capabilities', sa.JSON(), nullable=True))
    op.add_column('prometheus_configs', sa.Column('module_readiness', sa.JSON(), nullable=True))
    op.add_column('prometheus_configs', sa.Column('last_status', sa.String(40), nullable=True))
    op.add_column('prometheus_configs', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('prometheus_configs', sa.Column('last_response_time_ms', sa.Integer(), nullable=True))
    op.add_column('prometheus_configs', sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    for column in ('last_checked_at','last_response_time_ms','last_error','last_status','module_readiness','capabilities','capability_profile'):
        op.drop_column('prometheus_configs', column)
