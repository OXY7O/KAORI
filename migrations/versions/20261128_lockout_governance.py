"""Initialize the canonical authentication singleton without activating lockout (#5326)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_lockout_governance'
down_revision = '20261128_account_lockout'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deployment migration is exclusive; existing policy and secrets are untouched.
    op.execute(sa.text(
        'INSERT INTO authentication_security_policies (id, updated_at) '
        'SELECT 1, CURRENT_TIMESTAMP WHERE NOT EXISTS '
        '(SELECT 1 FROM authentication_security_policies WHERE id = 1)'
    ))


def downgrade() -> None:
    # The singleton belongs to all authentication controls. Never delete it.
    pass
