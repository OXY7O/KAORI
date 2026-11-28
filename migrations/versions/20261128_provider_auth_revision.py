"""Monotonic provider authentication revision for in-flight proof fencing (#5365)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_provider_auth_revision'
down_revision = '20261128_mfa_replacement'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'identity_providers',
        sa.Column('authentication_revision', sa.BigInteger(), nullable=False, server_default=sa.text('1')),
    )


def downgrade() -> None:
    op.drop_column('identity_providers', 'authentication_revision')
