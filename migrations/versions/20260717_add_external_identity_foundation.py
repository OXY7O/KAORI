"""add external identity foundation

Revision ID: 20260717_external_identity
Revises: 20260716_simplify_profiles
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = '20260717_external_identity'
down_revision = '20260716_profile_names'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'identity_providers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('display_name', sa.String(length=150), nullable=False),
        sa.Column('provider_type', sa.String(length=30), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('jit_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('server_uri', sa.String(length=500)),
        sa.Column('base_dn', sa.String(length=500)),
        sa.Column('bind_dn', sa.String(length=500)),
        sa.Column('bind_password_env', sa.String(length=150)),
        sa.Column('user_filter', sa.String(length=500)),
        sa.Column('group_base_dn', sa.String(length=500)),
        sa.Column('group_filter', sa.String(length=500)),
        sa.Column('tls_mode', sa.String(length=20), nullable=False, server_default='ldaps'),
        sa.Column('connect_timeout_seconds', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('username_attribute', sa.String(length=100), nullable=False, server_default='sAMAccountName'),
        sa.Column('email_attribute', sa.String(length=100), nullable=False, server_default='mail'),
        sa.Column('display_name_attribute', sa.String(length=100), nullable=False, server_default='displayName'),
        sa.Column('stable_id_attribute', sa.String(length=100), nullable=False, server_default='objectGUID'),
        sa.Column('oidc_issuer', sa.String(length=500)),
        sa.Column('oidc_client_id', sa.String(length=255)),
        sa.Column('oidc_client_secret_env', sa.String(length=150)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('key', name='uq_identity_providers_key'),
    )
    op.create_index('ix_identity_providers_key', 'identity_providers', ['key'])
    op.create_index('ix_identity_providers_provider_type', 'identity_providers', ['provider_type'])
    op.create_index('ix_identity_providers_enabled', 'identity_providers', ['enabled'])

    op.create_table(
        'external_identity_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('identity_providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('external_username', sa.String(length=255)),
        sa.Column('distinguished_name', sa.String(length=1000)),
        sa.Column('email', sa.String(length=255)),
        sa.Column('display_name', sa.String(length=255)),
        sa.Column('projection_type', sa.String(length=30), nullable=False, server_default='administrative'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('provider_id', 'subject', name='uq_external_identity_provider_subject'),
        sa.UniqueConstraint('user_id', 'provider_id', name='uq_external_identity_user_provider'),
    )
    op.create_index('ix_external_identity_links_user_id', 'external_identity_links', ['user_id'])
    op.create_index('ix_external_identity_links_provider_id', 'external_identity_links', ['provider_id'])
    op.create_index('ix_external_identity_links_subject', 'external_identity_links', ['subject'])
    op.create_index('ix_external_identity_links_external_username', 'external_identity_links', ['external_username'])


def downgrade():
    op.drop_table('external_identity_links')
    op.drop_table('identity_providers')
