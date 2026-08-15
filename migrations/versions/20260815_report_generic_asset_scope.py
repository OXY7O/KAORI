"""Add generic report asset scope for multi-domain report generation."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260815_report_asset_scope'
down_revision = '20260814_report_notify_channels'
branch_labels = None
depends_on = None


def _add_scope_columns(table: str) -> None:
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(sa.Column('scope_asset_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('scope_asset_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('scope_asset_label_snapshot', sa.String(length=255), nullable=True))
        batch_op.create_index(f'ix_{table}_scope_asset_type', ['scope_asset_type'], unique=False)
        batch_op.create_index(f'ix_{table}_scope_asset_id', ['scope_asset_id'], unique=False)


def _drop_scope_columns(table: str) -> None:
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_index(f'ix_{table}_scope_asset_id')
        batch_op.drop_index(f'ix_{table}_scope_asset_type')
        batch_op.drop_column('scope_asset_label_snapshot')
        batch_op.drop_column('scope_asset_id')
        batch_op.drop_column('scope_asset_type')


def upgrade() -> None:
    _add_scope_columns('reports')
    _add_scope_columns('report_schedules')
    op.execute(
        "UPDATE reports SET scope_asset_type='kubernetes_cluster', scope_asset_id=cluster_id "
        "WHERE cluster_id IS NOT NULL AND scope_asset_id IS NULL"
    )
    op.execute(
        "UPDATE report_schedules SET scope_asset_type='kubernetes_cluster', scope_asset_id=cluster_id "
        "WHERE cluster_id IS NOT NULL AND scope_asset_id IS NULL"
    )


def downgrade() -> None:
    _drop_scope_columns('report_schedules')
    _drop_scope_columns('reports')
