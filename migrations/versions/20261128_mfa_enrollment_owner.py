"""Bind inactive MFA setup to its originating authentication context (#5346)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_mfa_enrollment_owner'
down_revision = '20261128_auto_run_adoption'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No historical ownership backfill: unbound inactive setup must restart.
    op.add_column('authentication_mfa_factors', sa.Column('enrollment_generation', sa.BigInteger(), nullable=True))
    op.add_column('authentication_mfa_factors', sa.Column('enrollment_authenticated', sa.Boolean(), nullable=True))


def downgrade() -> None:
    # Do not make previously guarded pending seeds valid under the old schema.
    op.execute(sa.text('DELETE FROM authentication_mfa_factors WHERE enabled = false'))
    op.drop_column('authentication_mfa_factors', 'enrollment_authenticated')
    op.drop_column('authentication_mfa_factors', 'enrollment_generation')
