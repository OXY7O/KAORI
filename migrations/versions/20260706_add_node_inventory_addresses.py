"""add node inventory addresses

Revision ID: 20260706_node_addresses
Revises: 20260705_report_domain
Create Date: 2026-07-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '20260706_node_addresses'
down_revision = '20260705_report_domain'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('node_inventory', sa.Column('internal_ip', sa.String(length=64), nullable=True))
    op.add_column('node_inventory', sa.Column('external_ip', sa.String(length=64), nullable=True))
    op.add_column('node_inventory', sa.Column('hostname_address', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('node_inventory', 'hostname_address')
    op.drop_column('node_inventory', 'external_ip')
    op.drop_column('node_inventory', 'internal_ip')
