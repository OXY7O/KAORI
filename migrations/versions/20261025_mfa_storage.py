"""Add KAORI MFA factors and neutral authentication security policy (#3134).

Revision ID: 20261025_mfa_storage
Revises: 20261023_delivery_identity
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261025_mfa_storage'
down_revision = '20261023_delivery_identity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'authentication_security_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('mfa_mode', sa.String(32), nullable=False, server_default='disabled'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'authentication_mfa_factors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('totp_secret', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('recovery_hashes', sa.JSON(), nullable=False),
        sa.Column('last_accepted_step', sa.BigInteger(), nullable=True),
        sa.Column('enrollment_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', name='uq_auth_mfa_user'),
    )
    op.create_index('ix_authentication_mfa_factors_user_id', 'authentication_mfa_factors', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_authentication_mfa_factors_user_id', table_name='authentication_mfa_factors')
    op.drop_table('authentication_mfa_factors')
    op.drop_table('authentication_security_policies')
