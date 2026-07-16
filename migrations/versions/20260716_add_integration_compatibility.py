"""add integration and kubernetes compatibility state

Revision ID: 20260716_integration_compat
Revises: 20260714_ns_reveal_policy
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_integration_compat'
down_revision = '20260714_ns_reveal_policy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ('prometheus_configs', 'alertmanager_configs'):
        op.add_column(table, sa.Column('detected_version', sa.String(length=64), nullable=True))
        op.add_column(table, sa.Column('compatibility_status', sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column('compatibility_profile', sa.String(length=100), nullable=True))
        op.add_column(table, sa.Column('readiness_status', sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column('validation_message', sa.Text(), nullable=True))
        op.add_column(table, sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('clusters', sa.Column('kubernetes_version', sa.String(length=64), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_platform', sa.String(length=100), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_compatibility_status', sa.String(length=40), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_compatibility_profile', sa.String(length=100), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_readiness_status', sa.String(length=40), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_validation_message', sa.Text(), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_last_validated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in ('kubernetes_last_validated_at', 'kubernetes_validation_message', 'kubernetes_readiness_status', 'kubernetes_compatibility_profile', 'kubernetes_compatibility_status', 'kubernetes_platform', 'kubernetes_version'):
        op.drop_column('clusters', column)
    for table in ('alertmanager_configs', 'prometheus_configs'):
        for column in ('last_validated_at', 'validation_message', 'readiness_status', 'compatibility_profile', 'compatibility_status', 'detected_version'):
            op.drop_column(table, column)
