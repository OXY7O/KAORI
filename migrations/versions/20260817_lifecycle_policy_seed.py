"""Seed persisted lifecycle policies for runtime and analytics domains."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260817_lifecycle_policy_seed'
down_revision = '20260816_schedule_run_evidence'
branch_labels = None
depends_on = None


def _policy_table():
    return sa.table(
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


def upgrade() -> None:
    bind = op.get_bind()
    policies = _policy_table()
    now = datetime.now(UTC)
    seeds = (
        {
            'domain': 'runtime_observation',
            'enabled': True,
            'hot_retention_days': 90,
            'archive_retention_days': 365,
            'batch_size': 5000,
            'operation_mode': 'archive_and_cleanup',
            'schedule_enabled': True,
            'schedule_hour': 3,
            'schedule_minute': 45,
            'protect_unreviewed': False,
            'protected_max_days': None,
            'settings_json': {
                'preserve_provider_identity': True,
                'preserve_capability_evidence': True,
            },
        },
        {
            'domain': 'analytics_snapshot',
            'enabled': True,
            'hot_retention_days': 30,
            'archive_retention_days': 180,
            'batch_size': 5000,
            'operation_mode': 'archive_and_cleanup',
            'schedule_enabled': True,
            'schedule_hour': 4,
            'schedule_minute': 15,
            'protect_unreviewed': False,
            'protected_max_days': None,
            'settings_json': {
                'preserve_dataset_identity': True,
                'preserve_materialized_payload': True,
                'cleanup_only_after_stale_grace': True,
            },
        },
    )
    for seed in seeds:
        exists = bind.execute(sa.select(policies.c.domain).where(policies.c.domain == seed['domain'])).scalar()
        if exists is None:
            bind.execute(policies.insert().values(**seed, created_at=now, updated_at=now))


def downgrade() -> None:
    # Policies may have been edited by operators after upgrade. Preserve them on
    # downgrade rather than deleting governed configuration and execution intent.
    pass
