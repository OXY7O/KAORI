"""add shared integration runtime observation history

Revision ID: 20260718_integration_runtime
Revises: 20260718_alertmanager_instances
"""

from alembic import op
import sqlalchemy as sa

revision = '20260718_integration_runtime'
down_revision = '20260718_alertmanager_instances'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'integration_runtime_observations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.String(80), nullable=False),
        sa.Column('instance_id', sa.String(120), nullable=False),
        sa.Column('instance_name', sa.String(180), nullable=False),
        sa.Column('trigger_type', sa.String(30), nullable=False),
        sa.Column('readiness', sa.String(40), nullable=False),
        sa.Column('health_status', sa.String(40), nullable=False),
        sa.Column('health_score', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('compatibility_profile', sa.String(120), nullable=True),
        sa.Column('capability_profile', sa.String(120), nullable=True),
        sa.Column('capability_snapshot', sa.JSON(), nullable=False),
        sa.Column('diagnostics', sa.JSON(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_integration_runtime_provider_instance',
        'integration_runtime_observations',
        ['provider', 'instance_id', 'observed_at'],
    )
    op.create_index(
        'ix_integration_runtime_health',
        'integration_runtime_observations',
        ['provider', 'health_status', 'observed_at'],
    )


def downgrade():
    op.drop_index('ix_integration_runtime_health', table_name='integration_runtime_observations')
    op.drop_index('ix_integration_runtime_provider_instance', table_name='integration_runtime_observations')
    op.drop_table('integration_runtime_observations')
