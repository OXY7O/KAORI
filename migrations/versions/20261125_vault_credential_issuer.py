"""Add inactive exact-scope credential issuer revision history (#5184).

Revision ID: 20261125_vault_cred_issuer
Revises: 20261124_auto_host_trust

No issuer, seed, trust anchor or active credential authority is created.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261125_vault_cred_issuer'
down_revision = '20261124_auto_host_trust'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'secrets_pki_vault_credential_issuer_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('provider_namespace', sa.String(255), nullable=False),
        sa.Column('mount', sa.String(160), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('lifecycle_status', sa.String(20), nullable=False),
        sa.Column('algorithm', sa.String(20), nullable=False),
        sa.Column('public_key_hex', sa.String(64), nullable=False),
        sa.Column('key_sha256', sa.String(64), nullable=False),
        sa.Column('deployment_ref', sa.String(64), nullable=False),
        sa.Column('evidence_ref', sa.String(64), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('approved_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            'integration_instance_id',
            'provider_namespace',
            'mount',
            'revision_number',
            name='uq_spki_vault_cred_issuer_revision',
        ),
        sa.CheckConstraint('revision_number > 0', name='ck_spki_cred_issuer_revision'),
        sa.CheckConstraint("mount <> '' AND mount NOT LIKE '%*%'", name='ck_spki_cred_issuer_mount'),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'active', 'revoked')", name='ck_spki_cred_issuer_state'),
        sa.CheckConstraint("algorithm = 'ed25519'", name='ck_spki_cred_issuer_algorithm'),
        sa.CheckConstraint('length(public_key_hex) = 64', name='ck_spki_cred_issuer_key'),
        sa.CheckConstraint('length(key_sha256) = 64', name='ck_spki_cred_issuer_digest'),
        sa.CheckConstraint('length(deployment_ref) = 64', name='ck_spki_cred_issuer_deployment'),
        sa.CheckConstraint('length(evidence_ref) = 64', name='ck_spki_cred_issuer_evidence'),
        sa.CheckConstraint('effective_until > effective_from', name='ck_spki_cred_issuer_window'),
        sa.CheckConstraint(
            "lifecycle_status <> 'active' OR"
            ' (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL'
            ' AND requested_by_user_id <> approved_by_user_id'
            ' AND recorded_by_user_id = approved_by_user_id'
            ' AND approved_at <= recorded_at AND recorded_at < effective_until)',
            name='ck_spki_cred_issuer_independent',
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(
        sa.text('SELECT COUNT(*) FROM secrets_pki_vault_credential_issuer_revisions')
    ).scalar_one()
    if count:
        raise RuntimeError('Credential issuer revision evidence must be retained before downgrade.')
    op.drop_table('secrets_pki_vault_credential_issuer_revisions')
