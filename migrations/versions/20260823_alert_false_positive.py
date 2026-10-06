"""allow false-positive alert case closure

Revision ID: 20260823_alert_false_positive
Revises: 20260822_alert_source_unknown
Create Date: 2026-08-23
"""

from alembic import op

revision = '20260823_alert_false_positive'
down_revision = '20260822_alert_source_unknown'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_alert_cases_closure_reason', 'alert_cases', type_='check')
    op.create_check_constraint(
        'ck_alert_cases_closure_reason',
        'alert_cases',
        "closure_reason IS NULL OR closure_reason IN ('resolved', 'manual_withdrawal', 'source_decommissioned', 'false_positive')",
    )


def downgrade() -> None:
    # The previous revision cannot represent false-positive closure explicitly.
    # Preserve historical closure instead of failing rollback.
    op.execute("UPDATE alert_cases SET closure_reason = 'manual_withdrawal' WHERE closure_reason = 'false_positive'")
    op.drop_constraint('ck_alert_cases_closure_reason', 'alert_cases', type_='check')
    op.create_check_constraint(
        'ck_alert_cases_closure_reason',
        'alert_cases',
        "closure_reason IS NULL OR closure_reason IN ('resolved', 'manual_withdrawal', 'source_decommissioned')",
    )
