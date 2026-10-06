"""add prometheus query profile validation evidence

Revision ID: 20260716_promql_profiles
Revises: 20260716_integration_compat
"""

from alembic import op
import sqlalchemy as sa

revision = '20260716_promql_profiles'
down_revision = '20260716_integration_compat'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('prometheus_configs', sa.Column('query_profile', sa.String(length=100), nullable=True))
    op.add_column('prometheus_configs', sa.Column('query_validation_status', sa.String(length=40), nullable=True))
    op.add_column('prometheus_configs', sa.Column('query_validation_summary', sa.JSON(), nullable=True))
    op.add_column('prometheus_configs', sa.Column('retention_validation_summary', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('prometheus_configs', 'retention_validation_summary')
    op.drop_column('prometheus_configs', 'query_validation_summary')
    op.drop_column('prometheus_configs', 'query_validation_status')
    op.drop_column('prometheus_configs', 'query_profile')
