"""remove duplicated Service Inventory presentation columns

Revision ID: 20260805_service_inventory_v2
Revises: 20260805_report_job_execution
"""

from alembic import op
import sqlalchemy as sa

revision = '20260805_service_inventory_v2'
down_revision = '20260805_report_job_execution'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('service_inventory', 'ports')
    op.drop_column('service_inventory', 'external_ip')


def downgrade() -> None:
    op.add_column('service_inventory', sa.Column('external_ip', sa.String(length=255), nullable=True))
    op.add_column('service_inventory', sa.Column('ports', sa.String(length=255), nullable=True))
