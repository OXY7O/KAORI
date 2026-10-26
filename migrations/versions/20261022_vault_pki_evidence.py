"""Commit safe public Vault PKI issuer/certificate evidence (HV-03, #2587).

Revision ID: 20261022_vault_pki_evidence
Revises: 20261022_secrets_pki_inventory
"""

from alembic import op
import sqlalchemy as sa

revision = '20261022_vault_pki_evidence'
down_revision = '20261022_secrets_pki_inventory'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vault_instances', sa.Column('pki_mounts', sa.JSON(), nullable=True))
    op.create_table(
        'secrets_pki_issuer_identities',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('provider_namespace', sa.String(length=255), nullable=False),
        sa.Column('mount', sa.String(length=160), nullable=False),
        sa.Column('provider_issuer_id', sa.String(length=36), nullable=False),
        sa.Column('observation_status', sa.String(length=30), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            'integration_instance_id',
            'provider_namespace',
            'mount',
            'provider_issuer_id',
            name='uq_secrets_pki_issuer_source',
        ),
    )
    op.create_index(
        'ix_secrets_pki_issuer_identities_integration_instance_id',
        'secrets_pki_issuer_identities',
        ['integration_instance_id'],
    )
    op.create_index(
        'ix_secrets_pki_issuer_scope',
        'secrets_pki_issuer_identities',
        ['integration_instance_id', 'provider_namespace', 'mount', 'last_observed_at'],
    )
    op.create_table(
        'secrets_pki_public_certificates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'issuer_identity_id',
            sa.String(length=36),
            sa.ForeignKey('secrets_pki_issuer_identities.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('fingerprint_sha256', sa.String(length=64), nullable=False),
        sa.Column('serial_hex', sa.String(length=100), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_ca', sa.Boolean(), nullable=True),
        sa.Column('self_issued', sa.Boolean(), nullable=False),
        sa.Column('chain_fingerprints', sa.String(length=520), nullable=False),
        sa.Column('observation_status', sa.String(length=30), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('issuer_identity_id', 'fingerprint_sha256', name='uq_secrets_pki_public_cert_issuer_fp'),
    )
    op.create_index(
        'ix_secrets_pki_public_certificates_issuer_identity_id',
        'secrets_pki_public_certificates',
        ['issuer_identity_id'],
    )
    op.create_table(
        'secrets_pki_pki_collection_states',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('provider_namespace', sa.String(length=255), nullable=False),
        sa.Column('mount', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('observed_issuer_count', sa.Integer(), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=250), nullable=True),
        sa.UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount', name='uq_secrets_pki_pki_collection_scope'
        ),
    )
    op.create_index(
        'ix_secrets_pki_pki_collection_states_integration_instance_id',
        'secrets_pki_pki_collection_states',
        ['integration_instance_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_secrets_pki_pki_collection_states_integration_instance_id', table_name='secrets_pki_pki_collection_states'
    )
    op.drop_table('secrets_pki_pki_collection_states')
    op.drop_index('ix_secrets_pki_public_certificates_issuer_identity_id', table_name='secrets_pki_public_certificates')
    op.drop_table('secrets_pki_public_certificates')
    op.drop_index('ix_secrets_pki_issuer_scope', table_name='secrets_pki_issuer_identities')
    op.drop_index(
        'ix_secrets_pki_issuer_identities_integration_instance_id', table_name='secrets_pki_issuer_identities'
    )
    op.drop_table('secrets_pki_issuer_identities')
    op.drop_column('vault_instances', 'pki_mounts')
