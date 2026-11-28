"""Add committed session deadlines and policy on existing authentication owners (#5282)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_auth_session_expiry'
down_revision = '20261128_auto_credential_proof'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No backfill: an already issued cookie has no trustworthy activity baseline.
    op.add_column('users', sa.Column('auth_session_issued_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('auth_session_activity_at', sa.DateTime(timezone=True), nullable=True))
    for name, value in (
        ('session_privileged_idle_minutes', 15),
        ('session_privileged_absolute_hours', 4),
        ('session_regular_idle_minutes', 30),
        ('session_regular_absolute_hours', 8),
        ('session_warning_minutes', 2),
    ):
        op.add_column(
            'authentication_security_policies',
            sa.Column(name, sa.Integer(), nullable=False, server_default=sa.text(str(value))),
        )
    op.add_column(
        'authentication_security_policies',
        sa.Column('session_regular_remember', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    # Invalidate existing generations before removing the expiry authority so
    # downgrading cannot silently admit cookies already expired under it.
    op.execute(sa.text('UPDATE users SET auth_session_version = auth_session_version + 1'))
    for name in (
        'session_regular_remember',
        'session_warning_minutes',
        'session_regular_absolute_hours',
        'session_regular_idle_minutes',
        'session_privileged_absolute_hours',
        'session_privileged_idle_minutes',
    ):
        op.drop_column('authentication_security_policies', name)
    op.drop_column('users', 'auth_session_activity_at')
    op.drop_column('users', 'auth_session_issued_at')
