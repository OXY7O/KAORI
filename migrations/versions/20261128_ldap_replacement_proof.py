"""Bind LDAP replacement to the provider revision and verified identity (#5374)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_ldap_replacement_proof'
down_revision = '20261128_provider_auth_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('authentication_mfa_factors', sa.Column('replacement_provider_proof', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Old code must never inherit provider-authorized pending replacement.
    op.execute(sa.text(
        'UPDATE authentication_mfa_factors SET replacement_totp_secret = NULL, '
        'replacement_generation = NULL, replacement_expires_at = NULL '
        'WHERE replacement_provider_proof IS NOT NULL'
    ))
    op.drop_column('authentication_mfa_factors', 'replacement_provider_proof')
