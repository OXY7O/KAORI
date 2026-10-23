"""Add protected shared GitHub App configuration for SC-02 (#2741).

Revision ID: 20261023_sc_app_credential
Revises: 20261023_sc_identity

No App or installation is seeded; encrypted keys are only written through
KAORI EncryptedText and the approved credential-registration service.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_sc_app_credential'
down_revision = '20261023_sc_identity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'source_control_github_app_credentials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('host_key', sa.String(255), nullable=False),
        sa.Column('native_app_id', sa.String(80), nullable=False),
        sa.Column('private_key_pem', sa.Text(), nullable=False),
        sa.Column('webhook_secret', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('host_key', 'native_app_id', name='uq_sc_github_app_credential'),
    )
    op.add_column(
        'source_control_installations',
        sa.Column('github_app_credential_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_sc_installation_app_credential',
        'source_control_installations',
        'source_control_github_app_credentials',
        ['github_app_credential_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_sc_installation_app_credential', 'source_control_installations', type_='foreignkey'
    )
    op.drop_column('source_control_installations', 'github_app_credential_id')
    op.drop_table('source_control_github_app_credentials')
