"""Link committed source webhook delivery to canonical JobExecution (#2742).

Revision ID: 20261023_sc_webhook_job_link
Revises: 20261023_sc_repo_collection

Nullable link keeps old authenticated transport evidence. No background
dispatch is activated by this migration or its installation.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_sc_webhook_job_link'
down_revision = '20261023_sc_repo_collection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'source_control_webhook_deliveries',
        sa.Column('dispatched_job_execution_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_sc_webhook_delivery_job_execution',
        'source_control_webhook_deliveries', 'job_executions',
        ['dispatched_job_execution_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_sc_webhook_delivery_job_execution',
        'source_control_webhook_deliveries', type_='foreignkey',
    )
    op.drop_column('source_control_webhook_deliveries', 'dispatched_job_execution_id')
