"""Track bounded Vault PKI stored-certificate evidence; excludes no_store certs (#2587).

Revision ID: 20261022_vault_stored_certs
Revises: 20261022_vault_pki_evidence
"""

from alembic import op
import sqlalchemy as sa

revision = '20261022_vault_stored_certs'
down_revision = '20261022_vault_pki_evidence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vault_instances', sa.Column('pki_stored_certs_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'secrets_pki_stored_cert_observations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(),
                  sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('provider_namespace', sa.String(255), nullable=False),
        sa.Column('mount', sa.String(160), nullable=False),
        sa.Column('serial_hex', sa.String(100), nullable=False),
        sa.Column('fingerprint_sha256', sa.String(64), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('observation_status', sa.String(30), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('integration_instance_id', 'provider_namespace', 'mount', 'serial_hex',
                            name='uq_secrets_pki_stored_cert_source_serial'),
    )
    op.create_index('ix_secrets_pki_stored_cert_observations_integration_instance_id',
                    'secrets_pki_stored_cert_observations', ['integration_instance_id'])
    op.create_index('ix_secrets_pki_stored_cert_scope', 'secrets_pki_stored_cert_observations',
                    ['integration_instance_id', 'provider_namespace', 'mount', 'last_observed_at'])
    op.create_table(
        'secrets_pki_stored_cert_collection_states',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(),
                  sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('provider_namespace', sa.String(255), nullable=False),
        sa.Column('mount', sa.String(160), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('observed_stored_certificate_count', sa.Integer(), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(250), nullable=True),
        sa.UniqueConstraint('integration_instance_id', 'provider_namespace', 'mount',
                            name='uq_secrets_pki_stored_cert_collection_scope'),
    )
    op.create_index('ix_spki_stored_cert_state_instance',
                    'secrets_pki_stored_cert_collection_states', ['integration_instance_id'])


def downgrade() -> None:
    op.drop_column('vault_instances', 'pki_stored_certs_enabled')
    op.drop_index('ix_spki_stored_cert_state_instance',
                  table_name='secrets_pki_stored_cert_collection_states')
    op.drop_table('secrets_pki_stored_cert_collection_states')
    op.drop_index('ix_secrets_pki_stored_cert_scope', table_name='secrets_pki_stored_cert_observations')
    op.drop_index('ix_secrets_pki_stored_cert_observations_integration_instance_id',
                  table_name='secrets_pki_stored_cert_observations')
    op.drop_table('secrets_pki_stored_cert_observations')
