"""remove derived Configuration Inventory columns

Revision ID: 20260805_config_inventory_v2
Revises: 20260805_ingress_inventory_v2
"""

from alembic import op
import sqlalchemy as sa

revision = '20260805_config_inventory_v2'
down_revision = '20260805_ingress_inventory_v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('configuration_inventory', 'payload_size_bytes')
    op.drop_column('configuration_inventory', 'key_count')


def downgrade() -> None:
    op.add_column(
        'configuration_inventory',
        sa.Column('key_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'configuration_inventory',
        sa.Column('payload_size_bytes', sa.Integer(), nullable=False, server_default='0'),
    )
    op.execute(
        """
        UPDATE configuration_inventory
        SET key_count = json_array_length(COALESCE(key_names, '[]'::json)),
            payload_size_bytes = 0
        """
    )
    op.alter_column('configuration_inventory', 'key_count', server_default=None)
    op.alter_column('configuration_inventory', 'payload_size_bytes', server_default=None)
