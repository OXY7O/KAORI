"""add prometheus compatibility detection mode

Revision ID: 20260716_prom_detection
Revises: 20260716_promql_profiles
"""

from alembic import op
import sqlalchemy as sa

revision = '20260716_prom_detection'
down_revision = '20260716_promql_profiles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'prometheus_configs',
        sa.Column('version_detection_mode', sa.String(length=20), nullable=False, server_default='automatic'),
    )
    op.add_column('prometheus_configs', sa.Column('manual_compatibility_profile', sa.String(length=100), nullable=True))
    op.alter_column('prometheus_configs', 'version_detection_mode', server_default=None)


def downgrade() -> None:
    op.drop_column('prometheus_configs', 'manual_compatibility_profile')
    op.drop_column('prometheus_configs', 'version_detection_mode')
