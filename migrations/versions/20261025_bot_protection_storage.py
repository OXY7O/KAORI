"""Extend KAORI-owned authentication security policy for Turnstile (#3137).

Revision ID: 20261025_bot_protection
Revises: 20261025_mfa_storage
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261025_bot_protection'
down_revision = '20261025_mfa_storage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'authentication_security_policies',
        sa.Column('bot_mode', sa.String(24), nullable=False, server_default='disabled'),
    )
    op.add_column(
        'authentication_security_policies',
        sa.Column('bot_provider_key', sa.String(60), nullable=False, server_default='cloudflare_turnstile'),
    )
    op.add_column('authentication_security_policies', sa.Column('bot_site_key', sa.String(255)))
    op.add_column('authentication_security_policies', sa.Column('bot_secret_key', sa.Text()))
    op.add_column('authentication_security_policies', sa.Column('bot_hostname', sa.String(253)))
    op.add_column('authentication_security_policies', sa.Column('bot_tested_at', sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column('authentication_security_policies', 'bot_tested_at')
    op.drop_column('authentication_security_policies', 'bot_hostname')
    op.drop_column('authentication_security_policies', 'bot_secret_key')
    op.drop_column('authentication_security_policies', 'bot_site_key')
    op.drop_column('authentication_security_policies', 'bot_provider_key')
    op.drop_column('authentication_security_policies', 'bot_mode')
