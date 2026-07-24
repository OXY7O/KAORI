"""Add persistent analytics materialization snapshots.

Revision ID: 20260724_analytics_materialization
Revises: 20260724_job_orchestration
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = '20260724_analytics_materialization'
down_revision = '20260724_job_orchestration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'analytics_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('dataset_key', sa.String(length=120), nullable=False),
        sa.Column('parameter_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('parameters_json', sa.JSON(), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('freshness_minutes', sa.Integer(), nullable=False),
        sa.Column('stale_grace_minutes', sa.Integer(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_job_execution_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name='ck_analytics_snapshot_status',
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['last_job_execution_id'],
            ['job_executions.id'],
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'cluster_id',
            'dataset_key',
            'parameter_fingerprint',
            name='uq_analytics_snapshot_scope',
        ),
    )
    op.create_index(
        'ix_analytics_snapshots_lookup',
        'analytics_snapshots',
        ['cluster_id', 'dataset_key', 'parameter_fingerprint'],
        unique=False,
    )
    op.create_index(
        'ix_analytics_snapshots_freshness',
        'analytics_snapshots',
        ['status', 'expires_at'],
        unique=False,
    )
    op.create_index(
        'ix_analytics_snapshots_dataset_generated',
        'analytics_snapshots',
        ['dataset_key', 'generated_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_analytics_snapshots_cluster_id'),
        'analytics_snapshots',
        ['cluster_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_analytics_snapshots_expires_at'),
        'analytics_snapshots',
        ['expires_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_analytics_snapshots_last_job_execution_id'),
        'analytics_snapshots',
        ['last_job_execution_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_analytics_snapshots_last_job_execution_id'), table_name='analytics_snapshots')
    op.drop_index(op.f('ix_analytics_snapshots_expires_at'), table_name='analytics_snapshots')
    op.drop_index(op.f('ix_analytics_snapshots_cluster_id'), table_name='analytics_snapshots')
    op.drop_index('ix_analytics_snapshots_dataset_generated', table_name='analytics_snapshots')
    op.drop_index('ix_analytics_snapshots_freshness', table_name='analytics_snapshots')
    op.drop_index('ix_analytics_snapshots_lookup', table_name='analytics_snapshots')
    op.drop_table('analytics_snapshots')
