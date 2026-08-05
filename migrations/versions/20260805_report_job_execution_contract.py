"""link reports and schedule runs to canonical job executions

Revision ID: 20260805_report_job_execution_contract
Revises: 20260730_inventory_collection_evidence
"""
from alembic import op
import sqlalchemy as sa

revision = '20260805_report_job_execution_contract'
down_revision = '20260731_tls_evidence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reports', sa.Column('job_execution_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_reports_job_execution', 'reports', 'job_executions', ['job_execution_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_reports_job_execution_id', 'reports', ['job_execution_id'])
    op.add_column('report_schedule_runs', sa.Column('job_execution_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_report_schedule_runs_job_execution', 'report_schedule_runs', 'job_executions', ['job_execution_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_report_schedule_runs_job_execution_id', 'report_schedule_runs', ['job_execution_id'])


def downgrade() -> None:
    op.drop_index('ix_report_schedule_runs_job_execution_id', table_name='report_schedule_runs')
    op.drop_constraint('fk_report_schedule_runs_job_execution', 'report_schedule_runs', type_='foreignkey')
    op.drop_column('report_schedule_runs', 'job_execution_id')
    op.drop_index('ix_reports_job_execution_id', table_name='reports')
    op.drop_constraint('fk_reports_job_execution', 'reports', type_='foreignkey')
    op.drop_column('reports', 'job_execution_id')
