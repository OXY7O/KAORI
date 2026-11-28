"""Persist durable Plan/Run reservation correlation (#4801)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_auto_run_adoption'
down_revision = '20261128_auto_run_target_claim'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'automation_run_reservation_adoptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reservation_id', sa.String(36), nullable=False),
        sa.Column('plan_job_id', sa.Integer(), sa.ForeignKey('job_executions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('run_job_id', sa.Integer(), sa.ForeignKey('job_executions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('adopted_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('adopted_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('reservation_id', name='uq_auto_adoption_reservation'),
        sa.UniqueConstraint('plan_job_id', name='uq_auto_adoption_plan'),
        sa.UniqueConstraint('run_job_id', name='uq_auto_adoption_run'),
        sa.CheckConstraint('plan_job_id != run_job_id', name='ck_auto_adoption_distinct_jobs'),
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM automation_run_reservation_adoptions')).scalar_one()
    if count:
        raise RuntimeError('Run reservation adoption history must be retained before downgrade.')
    op.drop_table('automation_run_reservation_adoptions')
