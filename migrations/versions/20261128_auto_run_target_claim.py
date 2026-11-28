"""Persist non-authorizing pilot target reservations (#4801)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_auto_run_target_claim'
down_revision = '20261128_auth_session_expiry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'automation_run_target_claims',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reservation_id', sa.String(36), nullable=False),
        sa.Column('plan_job_id', sa.Integer(), sa.ForeignKey('job_executions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('resource_key', sa.String(120), nullable=False),
        sa.Column('active_resource_key', sa.String(120), nullable=True),
        sa.Column('plan_fingerprint', sa.String(64), nullable=False),
        sa.Column('reserved_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reserved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('plan_job_id', 'resource_key', name='uq_auto_run_plan_resource'),
        sa.UniqueConstraint('active_resource_key', name='uq_auto_run_active_resource'),
        sa.CheckConstraint(
            '(released_at IS NULL AND active_resource_key IS NOT NULL AND active_resource_key = resource_key)'
            ' OR (released_at IS NOT NULL AND active_resource_key IS NULL AND released_at >= reserved_at)',
            name='ck_auto_run_claim_lifecycle',
        ),
        sa.CheckConstraint('length(plan_fingerprint) = 64', name='ck_auto_run_claim_plan'),
    )
    op.create_index('ix_auto_run_reservation', 'automation_run_target_claims', ['reservation_id'])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM automation_run_target_claims')).scalar_one()
    if count:
        raise RuntimeError('Target reservation history must be retained before downgrade.')
    op.drop_index('ix_auto_run_reservation', table_name='automation_run_target_claims')
    op.drop_table('automation_run_target_claims')
