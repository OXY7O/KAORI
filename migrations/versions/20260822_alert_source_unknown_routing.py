"""add unknown source and reversible alert routing lifecycle

Revision ID: 20260822_alert_source_unknown
Revises: 20260822_alert_mgmt_foundation
Create Date: 2026-08-22
"""

import sqlalchemy as sa
from alembic import op

revision = '20260822_alert_source_unknown'
down_revision = '20260822_alert_mgmt_foundation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_alert_cases_source_state', 'alert_cases', type_='check')
    op.create_check_constraint(
        'ck_alert_cases_source_state',
        'alert_cases',
        "source_state IN ('firing', 'resolved', 'unknown')",
    )

    op.add_column('alert_cases', sa.Column('source_state_reason', sa.String(64), nullable=True))
    op.add_column('alert_cases', sa.Column('source_state_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'alert_cases',
        sa.Column('routing_state', sa.String(24), nullable=False, server_default='enabled'),
    )
    op.add_column('alert_cases', sa.Column('routing_override_reason', sa.String(64), nullable=True))
    op.add_column('alert_cases', sa.Column('routing_override_note', sa.Text(), nullable=True))
    op.add_column('alert_cases', sa.Column('routing_override_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alert_cases', sa.Column('routing_override_by_user_id', sa.Integer(), nullable=True))
    op.add_column('alert_cases', sa.Column('closure_reason', sa.String(40), nullable=True))
    op.create_foreign_key(
        'fk_alert_cases_routing_override_by_user_id_users',
        'alert_cases',
        'users',
        ['routing_override_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_check_constraint(
        'ck_alert_cases_routing_state',
        'alert_cases',
        "routing_state IN ('enabled', 'suppressed')",
    )
    op.create_check_constraint(
        'ck_alert_cases_closure_reason',
        'alert_cases',
        "closure_reason IS NULL OR closure_reason IN ('resolved', 'manual_withdrawal', 'source_decommissioned')",
    )
    op.create_index(
        'ix_alert_cases_source_changed',
        'alert_cases',
        ['source_state', 'source_state_changed_at'],
    )
    op.create_index(
        'ix_alert_cases_routing_state',
        'alert_cases',
        ['routing_state', 'routing_override_reason'],
    )
    op.create_index('ix_alert_cases_routing_override_reason', 'alert_cases', ['routing_override_reason'])
    op.create_index('ix_alert_cases_closure_reason', 'alert_cases', ['closure_reason'])

    cases = sa.table(
        'alert_cases',
        sa.column('workflow_state', sa.String()),
        sa.column('closure_reason', sa.String()),
    )
    op.execute(
        cases.update()
        .where(cases.c.workflow_state == 'closed')
        .where(cases.c.closure_reason.is_(None))
        .values(closure_reason='resolved')
    )

    op.add_column(
        'recommendation_alert_states',
        sa.Column('promotion_suppressed_until_clear', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'recommendation_alert_states',
        sa.Column('promotion_suppression_reason', sa.String(64), nullable=True),
    )


def downgrade() -> None:
    # The previous revision cannot represent Unknown. Preserve open incident evidence
    # by mapping Unknown back to Firing rather than allowing downgrade to fail its check.
    cases = sa.table(
        'alert_cases',
        sa.column('source_state', sa.String()),
    )
    op.execute(cases.update().where(cases.c.source_state == 'unknown').values(source_state='firing'))

    op.drop_column('recommendation_alert_states', 'promotion_suppression_reason')
    op.drop_column('recommendation_alert_states', 'promotion_suppressed_until_clear')

    op.drop_index('ix_alert_cases_closure_reason', table_name='alert_cases')
    op.drop_index('ix_alert_cases_routing_override_reason', table_name='alert_cases')
    op.drop_index('ix_alert_cases_routing_state', table_name='alert_cases')
    op.drop_index('ix_alert_cases_source_changed', table_name='alert_cases')
    op.drop_constraint('ck_alert_cases_closure_reason', 'alert_cases', type_='check')
    op.drop_constraint('ck_alert_cases_routing_state', 'alert_cases', type_='check')
    op.drop_constraint('fk_alert_cases_routing_override_by_user_id_users', 'alert_cases', type_='foreignkey')
    op.drop_column('alert_cases', 'closure_reason')
    op.drop_column('alert_cases', 'routing_override_by_user_id')
    op.drop_column('alert_cases', 'routing_override_at')
    op.drop_column('alert_cases', 'routing_override_note')
    op.drop_column('alert_cases', 'routing_override_reason')
    op.drop_column('alert_cases', 'routing_state')
    op.drop_column('alert_cases', 'source_state_changed_at')
    op.drop_column('alert_cases', 'source_state_reason')

    op.drop_constraint('ck_alert_cases_source_state', 'alert_cases', type_='check')
    op.create_check_constraint(
        'ck_alert_cases_source_state',
        'alert_cases',
        "source_state IN ('firing', 'resolved')",
    )
