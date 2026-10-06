"""add report schedules

Revision ID: 20260705_report_schedules
Revises: 20260705_report_templates
Create Date: 2026-07-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '20260705_report_schedules'
down_revision = '20260705_report_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'report_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=True),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('period', sa.String(length=50), nullable=False),
        sa.Column('output_format', sa.String(length=50), nullable=False),
        sa.Column('sections', sa.JSON(), nullable=False),
        sa.Column('cadence', sa.String(length=50), nullable=False),
        sa.Column('run_time', sa.String(length=5), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(length=80), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=50), nullable=True),
        sa.Column('last_report_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_by_username_snapshot', sa.String(length=100), nullable=True),
        sa.Column('created_by_display_name_snapshot', sa.String(length=150), nullable=True),
        sa.Column('created_by_auth_source_snapshot', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['last_report_id'], ['reports.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('report_schedules', schema=None) as batch_op:
        batch_op.create_index('ix_report_schedules_name', ['name'], unique=False)
        batch_op.create_index('ix_report_schedules_report_type', ['report_type'], unique=False)
        batch_op.create_index('ix_report_schedules_cluster_id', ['cluster_id'], unique=False)
        batch_op.create_index('ix_report_schedules_namespace', ['namespace'], unique=False)
        batch_op.create_index('ix_report_schedules_cadence', ['cadence'], unique=False)
        batch_op.create_index('ix_report_schedules_is_enabled', ['is_enabled'], unique=False)
        batch_op.create_index('ix_report_schedules_next_run_at', ['next_run_at'], unique=False)
        batch_op.create_index('ix_report_schedules_last_status', ['last_status'], unique=False)
        batch_op.create_index('ix_report_schedules_last_report_id', ['last_report_id'], unique=False)
        batch_op.create_index('ix_report_schedules_created_by_id', ['created_by_id'], unique=False)
        batch_op.create_index('ix_report_schedules_created_at', ['created_at'], unique=False)

    op.create_table(
        'report_schedule_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=True),
        sa.Column('report_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('trigger_source', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['schedule_id'], ['report_schedules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('report_schedule_runs', schema=None) as batch_op:
        batch_op.create_index('ix_report_schedule_runs_schedule_id', ['schedule_id'], unique=False)
        batch_op.create_index('ix_report_schedule_runs_report_id', ['report_id'], unique=False)
        batch_op.create_index('ix_report_schedule_runs_status', ['status'], unique=False)
        batch_op.create_index('ix_report_schedule_runs_trigger_source', ['trigger_source'], unique=False)
        batch_op.create_index('ix_report_schedule_runs_started_at', ['started_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('report_schedule_runs', schema=None) as batch_op:
        batch_op.drop_index('ix_report_schedule_runs_started_at')
        batch_op.drop_index('ix_report_schedule_runs_trigger_source')
        batch_op.drop_index('ix_report_schedule_runs_status')
        batch_op.drop_index('ix_report_schedule_runs_report_id')
        batch_op.drop_index('ix_report_schedule_runs_schedule_id')
    op.drop_table('report_schedule_runs')

    with op.batch_alter_table('report_schedules', schema=None) as batch_op:
        batch_op.drop_index('ix_report_schedules_created_at')
        batch_op.drop_index('ix_report_schedules_created_by_id')
        batch_op.drop_index('ix_report_schedules_last_report_id')
        batch_op.drop_index('ix_report_schedules_last_status')
        batch_op.drop_index('ix_report_schedules_next_run_at')
        batch_op.drop_index('ix_report_schedules_is_enabled')
        batch_op.drop_index('ix_report_schedules_cadence')
        batch_op.drop_index('ix_report_schedules_namespace')
        batch_op.drop_index('ix_report_schedules_cluster_id')
        batch_op.drop_index('ix_report_schedules_report_type')
        batch_op.drop_index('ix_report_schedules_name')
    op.drop_table('report_schedules')
