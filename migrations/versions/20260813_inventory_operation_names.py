"""clarify inventory job operation names

Revision ID: 20260813_inventory_op_names
Revises: 20260813_obj_storage_jobs
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260813_inventory_op_names'
down_revision = '20260813_obj_storage_jobs'
branch_labels = None
depends_on = None

KUBERNETES_OLD = 'inventory_sync_all'
KUBERNETES_NEW = 'sync_kubernetes_inventory'
OBJECT_STORAGE_OLD = 'object_storage_inventory_sync_all'
OBJECT_STORAGE_NEW = 'sync_object_storage_inventory'


def _job_executions() -> sa.Table:
    return sa.table(
        'job_executions',
        sa.column('operation', sa.String),
    )


def upgrade() -> None:
    jobs = _job_executions()
    bind = op.get_bind()
    bind.execute(jobs.update().where(jobs.c.operation == KUBERNETES_OLD).values(operation=KUBERNETES_NEW))
    bind.execute(jobs.update().where(jobs.c.operation == OBJECT_STORAGE_OLD).values(operation=OBJECT_STORAGE_NEW))


def downgrade() -> None:
    jobs = _job_executions()
    bind = op.get_bind()
    bind.execute(jobs.update().where(jobs.c.operation == KUBERNETES_NEW).values(operation=KUBERNETES_OLD))
    bind.execute(jobs.update().where(jobs.c.operation == OBJECT_STORAGE_NEW).values(operation=OBJECT_STORAGE_OLD))
