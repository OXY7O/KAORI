"""Add governed Turnstile provider-instance and policy fields (#3137).

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
        sa.Column('bot_mode', sa.String(16), nullable=False, server_default='disabled'),
    )
    op.add_column(
        'authentication_security_policies',
        sa.Column('bot_provider_key', sa.String(80), nullable=False, server_default='cloudflare_turnstile'),
    )
    op.add_column('authentication_security_policies', sa.Column('bot_site_key', sa.String(255), nullable=True))
    op.add_column('authentication_security_policies', sa.Column('bot_secret', sa.Text(), nullable=True))
    op.add_column('authentication_security_policies', sa.Column('bot_hostname', sa.String(253), nullable=True))


def downgrade() -> None:
    op.drop_column('authentication_security_policies', 'bot_hostname')
    op.drop_column('authentication_security_policies', 'bot_secret')
    op.drop_column('authentication_security_policies', 'bot_site_key')
    op.drop_column('authentication_security_policies', 'bot_provider_key')
    op.drop_column('authentication_security_policies', 'bot_mode')
