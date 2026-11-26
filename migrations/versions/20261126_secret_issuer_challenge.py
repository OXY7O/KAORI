"""Add inactive issuer challenge metadata (#5235).

Revision ID: 20261126_spki_issuer_challenge
Revises: 20261125_spki_cred_issuer

No challenge issuance, seed, trust anchor or operational authority.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261126_spki_issuer_challenge'
down_revision = '20261125_spki_cred_issuer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'secrets_pki_credential_issuer_challenges',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('provider_key', sa.String(80), nullable=False),
        sa.Column('provider_namespace', sa.String(255), nullable=False),
        sa.Column('mount', sa.String(160), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('deployment_ref', sa.String(64), nullable=False),
        sa.Column('key_sha256', sa.String(64), nullable=False),
        sa.Column('challenge_sha256', sa.String(64), nullable=False),
        sa.Column('source_owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lifecycle_status', sa.String(20), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('possession_evidence_ref', sa.String(64), nullable=True),
        sa.UniqueConstraint('challenge_sha256', name='uq_spki_challenge_digest'),
        sa.CheckConstraint("provider_key IN ('vault', 'openbao')", name='ck_spki_challenge_provider'),
        sa.CheckConstraint(
            "provider_namespace NOT LIKE '%*%' AND provider_namespace NOT LIKE '%+%'",
            name='ck_spki_challenge_namespace',
        ),
        sa.CheckConstraint(
            "mount <> '' AND mount NOT LIKE '%*%' AND mount NOT LIKE '%+%'", name='ck_spki_challenge_mount'
        ),
        sa.CheckConstraint('revision_number > 0', name='ck_spki_challenge_revision'),
        sa.CheckConstraint('length(deployment_ref) = 64', name='ck_spki_challenge_deployment'),
        sa.CheckConstraint('length(key_sha256) = 64', name='ck_spki_challenge_key'),
        sa.CheckConstraint('length(challenge_sha256) = 64', name='ck_spki_challenge_digest'),
        sa.CheckConstraint('expires_at > issued_at', name='ck_spki_challenge_window'),
        sa.CheckConstraint("lifecycle_status IN ('pending', 'consumed', 'revoked')", name='ck_spki_challenge_state'),
        sa.CheckConstraint(
            "(lifecycle_status = 'pending' AND resolved_at IS NULL"
            ' AND resolved_by_user_id IS NULL AND possession_evidence_ref IS NULL)'
            " OR (lifecycle_status = 'consumed' AND resolved_at IS NOT NULL"
            ' AND resolved_by_user_id IS NOT NULL AND resolved_by_user_id <> source_owner_id'
            ' AND resolved_at >= issued_at AND resolved_at < expires_at'
            ' AND possession_evidence_ref IS NOT NULL AND length(possession_evidence_ref) = 64)'
            " OR (lifecycle_status = 'revoked' AND resolved_at IS NOT NULL"
            ' AND resolved_by_user_id IS NOT NULL AND resolved_at >= issued_at'
            ' AND possession_evidence_ref IS NULL)',
            name='ck_spki_challenge_resolution',
        ),
    )
    op.create_index(
        'ix_spki_challenge_scope',
        'secrets_pki_credential_issuer_challenges',
        ['integration_instance_id', 'provider_namespace', 'mount', 'revision_number'],
    )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(sa.text('SELECT COUNT(*) FROM secrets_pki_credential_issuer_challenges')).scalar_one()
    if count:
        raise RuntimeError('Issuer challenge evidence must be retained before downgrade.')
    op.drop_index('ix_spki_challenge_scope', table_name='secrets_pki_credential_issuer_challenges')
    op.drop_table('secrets_pki_credential_issuer_challenges')
