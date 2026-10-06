"""Retain schedule contract evidence on report schedule runs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260816_schedule_run_evidence'
down_revision = '20260816_report_lifecycle'
branch_labels = None
depends_on = None


def _has_schedule_snapshot(bind) -> bool:
    return any(
        str(column.get('name') or '') == 'schedule_snapshot'
        for column in sa.inspect(bind).get_columns('report_schedule_runs')
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_schedule_snapshot(bind):
        op.add_column('report_schedule_runs', sa.Column('schedule_snapshot', sa.JSON(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE report_schedule_runs AS r
            SET schedule_snapshot = json_build_object(
                'name', s.name,
                'report_type', s.report_type,
                'report_domain', s.report_domain,
                'scope_asset_type', s.scope_asset_type,
                'scope_asset_id', COALESCE(s.scope_asset_id, s.cluster_id),
                'scope_asset_label', s.scope_asset_label_snapshot,
                'namespace', s.namespace,
                'period', s.period,
                'output_format', s.output_format,
                'sections', s.sections,
                'cadence', s.cadence,
                'run_time', s.run_time,
                'day_of_week', s.day_of_week,
                'day_of_month', s.day_of_month,
                'timezone', s.timezone
            )
            FROM report_schedules AS s
            WHERE r.schedule_id = s.id
              AND r.schedule_snapshot IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_schedule_snapshot(bind):
        op.drop_column('report_schedule_runs', 'schedule_snapshot')
