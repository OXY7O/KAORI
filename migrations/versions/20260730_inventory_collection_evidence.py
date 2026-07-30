"""Add committed inventory collection evidence.

Revision ID: 20260730_inventory_evidence
Revises: 20260729_report_delivery
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa

revision = '20260730_inventory_evidence'
down_revision = '20260729_report_delivery'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('cluster_inventory') as batch:
        batch.add_column(sa.Column('collection_evidence', sa.JSON(), nullable=True))
    op.execute("UPDATE cluster_inventory SET collection_evidence = '{}' WHERE collection_evidence IS NULL")
    with op.batch_alter_table('cluster_inventory') as batch:
        batch.alter_column('collection_evidence', nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('cluster_inventory') as batch:
        batch.drop_column('collection_evidence')
