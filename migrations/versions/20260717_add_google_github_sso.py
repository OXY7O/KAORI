"""add Google and GitHub SSO provider policy

Revision ID: 20260717_google_github_sso
Revises: 20260717_external_identity
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa

revision = '20260717_google_github_sso'
down_revision = '20260717_external_identity'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('identity_providers', sa.Column('default_role_id', sa.Integer(), nullable=True))
    op.add_column('identity_providers', sa.Column('allowed_domains', sa.Text(), nullable=True))
    op.add_column('identity_providers', sa.Column('allowed_subjects', sa.Text(), nullable=True))
    op.create_index('ix_identity_providers_default_role_id', 'identity_providers', ['default_role_id'])
    op.create_foreign_key(
        'fk_identity_providers_default_role_id_roles',
        'identity_providers',
        'roles',
        ['default_role_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_identity_providers_default_role_id_roles', 'identity_providers', type_='foreignkey')
    op.drop_index('ix_identity_providers_default_role_id', table_name='identity_providers')
    op.drop_column('identity_providers', 'allowed_subjects')
    op.drop_column('identity_providers', 'allowed_domains')
    op.drop_column('identity_providers', 'default_role_id')
