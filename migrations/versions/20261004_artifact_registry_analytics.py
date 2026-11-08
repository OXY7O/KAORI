"""add Artifact Registry analytics snapshots

Revision ID: 20261004_registry_analytics
Revises: 20261004_registry_governance
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20261004_registry_analytics'
down_revision = '20261004_registry_governance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'registry_analytics_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('time_range', sa.String(length=20), nullable=False, server_default='current'),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ready'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('freshness_minutes', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('stale_grace_minutes', sa.Integer(), nullable=False, server_default='1440'),
        sa.Column('last_job_execution_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['last_job_execution_id'], ['job_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('registry_analytics_snapshots', 'time_range', server_default=None)
    op.alter_column('registry_analytics_snapshots', 'status', server_default=None)
    op.alter_column('registry_analytics_snapshots', 'freshness_minutes', server_default=None)
    op.alter_column('registry_analytics_snapshots', 'stale_grace_minutes', server_default=None)
    op.create_index(
        'ix_registry_analytics_snapshots_integration_instance_id',
        'registry_analytics_snapshots',
        ['integration_instance_id'],
    )
    op.create_index(
        'ix_registry_analytics_snapshots_expires_at',
        'registry_analytics_snapshots',
        ['expires_at'],
    )
    op.create_index(
        'ix_registry_analytics_snapshots_last_job_execution_id',
        'registry_analytics_snapshots',
        ['last_job_execution_id'],
    )
    op.create_index(
        'ix_registry_analytics_instance_generated',
        'registry_analytics_snapshots',
        ['integration_instance_id', 'generated_at'],
    )
    op.create_index(
        'ix_registry_analytics_freshness',
        'registry_analytics_snapshots',
        ['status', 'expires_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_registry_analytics_freshness', table_name='registry_analytics_snapshots')
    op.drop_index('ix_registry_analytics_instance_generated', table_name='registry_analytics_snapshots')
    op.drop_index('ix_registry_analytics_snapshots_last_job_execution_id', table_name='registry_analytics_snapshots')
    op.drop_index('ix_registry_analytics_snapshots_expires_at', table_name='registry_analytics_snapshots')
    op.drop_index('ix_registry_analytics_snapshots_integration_instance_id', table_name='registry_analytics_snapshots')
    op.drop_table('registry_analytics_snapshots')
