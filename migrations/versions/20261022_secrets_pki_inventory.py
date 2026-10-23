"""Add canonical Secret identities and safe KV v2 representations (HV-02, #2586).

Revision ID: 20261022_secrets_pki_inventory
Revises: 20261022_vault_provider
"""

from alembic import op
import sqlalchemy as sa

revision = '20261022_secrets_pki_inventory'
down_revision = '20261022_vault_provider'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vault_instances', sa.Column('kv2_mounts', sa.JSON(), nullable=True))
    op.create_table(
        'secrets_pki_secret_identities',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('lifecycle_status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'secrets_pki_secret_representations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('secret_identity_id', sa.String(length=36), sa.ForeignKey('secrets_pki_secret_identities.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('provider_key', sa.String(length=80), nullable=False),
        sa.Column('provider_namespace', sa.String(length=255), nullable=False),
        sa.Column('mount', sa.String(length=160), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('path_sha256', sa.String(length=64), nullable=False),
        sa.Column('representation_role', sa.String(length=40), nullable=False),
        sa.Column('observation_status', sa.String(length=40), nullable=False),
        sa.Column('current_version', sa.Integer(), nullable=False),
        sa.Column('oldest_version', sa.Integer(), nullable=False),
        sa.Column('max_versions', sa.Integer(), nullable=False),
        sa.Column('cas_required', sa.Boolean(), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount', 'path_sha256',
            name='uq_secrets_pki_provider_representation',
        ),
    )
    op.create_index('ix_secrets_pki_secret_representations_secret_identity_id', 'secrets_pki_secret_representations', ['secret_identity_id'])
    op.create_index('ix_secrets_pki_secret_representations_integration_instance_id', 'secrets_pki_secret_representations', ['integration_instance_id'])
    op.create_index(
        'ix_secrets_pki_representation_scope',
        'secrets_pki_secret_representations',
        ['integration_instance_id', 'provider_namespace', 'mount', 'last_observed_at'],
    )
    op.create_table(
        'secrets_pki_secret_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('representation_id', sa.Integer(), sa.ForeignKey('secrets_pki_secret_representations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('provider_created_time', sa.String(length=80), nullable=True),
        sa.Column('provider_deletion_time', sa.String(length=80), nullable=True),
        sa.Column('destroyed', sa.Boolean(), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('representation_id', 'version', name='uq_secrets_pki_representation_version'),
    )
    op.create_index('ix_secrets_pki_secret_versions_representation_id', 'secrets_pki_secret_versions', ['representation_id'])
    op.create_table(
        'secrets_pki_inventory_collection_states',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(), sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('provider_namespace', sa.String(length=255), nullable=False),
        sa.Column('mount', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('observed_count', sa.Integer(), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=250), nullable=True),
        sa.UniqueConstraint(
            'integration_instance_id', 'provider_namespace', 'mount',
            name='uq_secrets_pki_inventory_scope',
        ),
    )
    op.create_index('ix_spki_inventory_state_instance',
                    'secrets_pki_inventory_collection_states', ['integration_instance_id'])


def downgrade() -> None:
    op.drop_column('vault_instances', 'kv2_mounts')
    op.drop_index('ix_spki_inventory_state_instance',
                  table_name='secrets_pki_inventory_collection_states')
    op.drop_table('secrets_pki_inventory_collection_states')
    op.drop_index('ix_secrets_pki_secret_versions_representation_id', table_name='secrets_pki_secret_versions')
    op.drop_table('secrets_pki_secret_versions')
    op.drop_index('ix_secrets_pki_representation_scope', table_name='secrets_pki_secret_representations')
    op.drop_index('ix_secrets_pki_secret_representations_integration_instance_id',
                  table_name='secrets_pki_secret_representations')
    op.drop_index('ix_secrets_pki_secret_representations_secret_identity_id',
                  table_name='secrets_pki_secret_representations')
    op.drop_table('secrets_pki_secret_representations')
    op.drop_table('secrets_pki_secret_identities')
