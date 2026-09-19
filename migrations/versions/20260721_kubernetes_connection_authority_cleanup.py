"""make KubernetesConnection the sole Kubernetes runtime authority

Revision ID: 20260721_k8s_authority
Revises: 20260721_integration_cutover
Create Date: 2026-07-21 19:10:00

Development-only destructive cleanup. Existing Kubernetes runtime metadata is
not migrated because KAORI can rediscover it through Full Validation.
"""

from alembic import op
import sqlalchemy as sa

revision = '20260721_k8s_authority'
down_revision = '20260721_integration_cutover'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('kubernetes_connections') as batch:
        batch.add_column(sa.Column('detected_version', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('detected_platform', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('compatibility_status', sa.String(length=40), nullable=True))
        batch.add_column(sa.Column('lifecycle_status', sa.String(length=20), nullable=True))

    with op.batch_alter_table('clusters') as batch:
        batch.drop_column('kubernetes_version')
        batch.drop_column('kubernetes_platform')
        batch.drop_column('kubernetes_compatibility_status')
        batch.drop_column('kubernetes_compatibility_profile')
        batch.drop_column('kubernetes_readiness_status')
        batch.drop_column('kubernetes_lifecycle_status')
        batch.drop_column('kubernetes_api_discovery_summary')
        batch.drop_column('kubernetes_validation_message')
        batch.drop_column('kubernetes_last_validated_at')


def downgrade() -> None:
    raise RuntimeError(
        'This development cleanup is intentionally irreversible. Reset the development database instead.'
    )
