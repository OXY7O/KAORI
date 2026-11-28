"""Store pending encrypted authenticator replacement without modifying active factors (#5357)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_mfa_replacement'
down_revision = '20261128_mfa_enrollment_owner'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('authentication_mfa_factors', sa.Column('replacement_totp_secret', sa.Text(), nullable=True))
    op.add_column('authentication_mfa_factors', sa.Column('replacement_generation', sa.BigInteger(), nullable=True))
    op.add_column(
        'authentication_mfa_factors', sa.Column('replacement_expires_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Only pending replacement is discarded; the authoritative factor stays intact.
    op.drop_column('authentication_mfa_factors', 'replacement_expires_at')
    op.drop_column('authentication_mfa_factors', 'replacement_generation')
    op.drop_column('authentication_mfa_factors', 'replacement_totp_secret')
