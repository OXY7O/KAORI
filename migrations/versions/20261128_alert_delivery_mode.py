"""Persist explicit recommendation alert routing mode (#5450)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_alert_delivery_mode'
down_revision = '20261128_lockout_governance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alert_delivery_modes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('mode', sa.String(24), nullable=False),
        sa.Column('revision', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_alert_delivery_mode_singleton'),
        sa.CheckConstraint(
            "mode IN ('channel_defaults', 'policy_required', 'delivery_disabled')",
            name='ck_alert_delivery_mode_value',
        ),
        sa.CheckConstraint('revision >= 1', name='ck_alert_delivery_mode_revision'),
    )
    op.execute(sa.text(
        "INSERT INTO alert_delivery_modes (id, mode, revision, updated_at) "
        "VALUES (1, 'channel_defaults', 1, CURRENT_TIMESTAMP)"
    ))


def downgrade() -> None:
    op.drop_table('alert_delivery_modes')
