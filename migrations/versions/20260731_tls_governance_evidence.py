"""Add TLS governance coverage and collection evidence.

Revision ID: 20260731_tls_evidence
Revises: 20260730_inventory_evidence
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa

revision = '20260731_tls_evidence'
down_revision = '20260730_inventory_evidence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('tls_certificate_inventory') as batch:
        batch.add_column(sa.Column('coverage_state', sa.String(length=50), nullable=False, server_default='not_reported'))
        batch.add_column(sa.Column('declared_host_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('covered_host_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('uncovered_hosts', sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
        batch.create_index('ix_tls_certificate_inventory_coverage_state', ['coverage_state'], unique=False)

    op.create_table(
        'tls_certificate_collection_states',
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('secret_collection_status', sa.String(length=50), nullable=False, server_default='not_reported'),
        sa.Column('ingress_mapping_status', sa.String(length=50), nullable=False, server_default='not_reported'),
        sa.Column('secret_collection_detail', sa.Text(), nullable=True),
        sa.Column('ingress_mapping_detail', sa.Text(), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('cluster_id'),
    )
    op.create_index(
        'ix_tls_certificate_collection_states_secret_collection_status',
        'tls_certificate_collection_states',
        ['secret_collection_status'],
        unique=False,
    )
    op.create_index(
        'ix_tls_certificate_collection_states_ingress_mapping_status',
        'tls_certificate_collection_states',
        ['ingress_mapping_status'],
        unique=False,
    )
    op.create_index(
        'ix_tls_certificate_collection_states_collected_at',
        'tls_certificate_collection_states',
        ['collected_at'],
        unique=False,
    )

    with op.batch_alter_table('tls_certificate_inventory') as batch:
        batch.alter_column('coverage_state', server_default=None)
        batch.alter_column('declared_host_count', server_default=None)
        batch.alter_column('covered_host_count', server_default=None)
        batch.alter_column('uncovered_hosts', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_tls_certificate_collection_states_collected_at', table_name='tls_certificate_collection_states')
    op.drop_index('ix_tls_certificate_collection_states_ingress_mapping_status', table_name='tls_certificate_collection_states')
    op.drop_index('ix_tls_certificate_collection_states_secret_collection_status', table_name='tls_certificate_collection_states')
    op.drop_table('tls_certificate_collection_states')

    with op.batch_alter_table('tls_certificate_inventory') as batch:
        batch.drop_index('ix_tls_certificate_inventory_coverage_state')
        batch.drop_column('uncovered_hosts')
        batch.drop_column('covered_host_count')
        batch.drop_column('declared_host_count')
        batch.drop_column('coverage_state')
