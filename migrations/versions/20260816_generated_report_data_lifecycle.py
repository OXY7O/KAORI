"""Add generated report data lifecycle policy and retention index."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260816_generated_report_lifecycle'
down_revision = '20260815_report_asset_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_reports_retention_boundary',
        'reports',
        ['status', 'updated_at', 'id'],
        unique=False,
    )

    bind = op.get_bind()
    policies = sa.table(
        'data_lifecycle_policies',
        sa.column('domain', sa.String),
        sa.column('enabled', sa.Boolean),
        sa.column('hot_retention_days', sa.Integer),
        sa.column('archive_retention_days', sa.Integer),
        sa.column('batch_size', sa.Integer),
        sa.column('operation_mode', sa.String),
        sa.column('schedule_enabled', sa.Boolean),
        sa.column('schedule_hour', sa.Integer),
        sa.column('schedule_minute', sa.Integer),
        sa.column('protect_unreviewed', sa.Boolean),
        sa.column('protected_max_days', sa.Integer),
        sa.column('settings_json', sa.JSON),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    exists = bind.execute(
        sa.select(policies.c.domain).where(policies.c.domain == 'generated_report')
    ).scalar()
    if exists is None:
        now = datetime.now(UTC)
        bind.execute(
            policies.insert().values(
                domain='generated_report',
                enabled=False,
                hot_retention_days=90,
                archive_retention_days=365,
                batch_size=250,
                operation_mode='archive_and_cleanup',
                schedule_enabled=False,
                schedule_hour=5,
                schedule_minute=0,
                protect_unreviewed=False,
                protected_max_days=None,
                settings_json={
                    'failed_retention_days': 30,
                    'archived_retention_days': 180,
                    'archive_binary_artifacts': True,
                    'protect_active_generation': True,
                },
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    policies = sa.table('data_lifecycle_policies', sa.column('domain', sa.String))
    bind.execute(policies.delete().where(policies.c.domain == 'generated_report'))
    op.drop_index('ix_reports_retention_boundary', table_name='reports')
