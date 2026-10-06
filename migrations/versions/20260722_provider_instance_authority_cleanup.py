"""Normalize Prometheus and Alertmanager shared authority.

Revision ID: 20260722_provider_authority
Revises: 20260721_k8s_authority
Create Date: 2026-07-22 10:00:00

Development-only destructive cleanup. Shared identity and runtime state live on
integration_instances. Provider tables retain only provider-specific connection
configuration and validation evidence. Existing development data is intentionally
not migrated; reset and bootstrap the development database.
"""

from alembic import op


revision = '20260722_provider_authority'
down_revision = '20260721_k8s_authority'
branch_labels = None
depends_on = None


_SHARED_COLUMNS = (
    'name',
    'description',
    'enabled',
    'readiness_status',
    'last_status',
    'last_error',
    'last_checked_at',
)


def upgrade() -> None:
    with op.batch_alter_table('prometheus_instances') as batch:
        for column_name in _SHARED_COLUMNS:
            batch.drop_column(column_name)

    with op.batch_alter_table('alertmanager_instances') as batch:
        batch.drop_index('ix_alertmanager_instances_readiness')
        batch.drop_index('ix_alertmanager_instances_status')
        for column_name in _SHARED_COLUMNS:
            batch.drop_column(column_name)


def downgrade() -> None:
    raise RuntimeError(
        'This development authority cleanup is intentionally irreversible. Reset the development database instead.'
    )
