"""Commit operator-attested internal PKI certificate metadata (#4461).

Revision ID: 20261112_internal_pki
Revises: 20261025_bot_protection

Only normalized public certificate identity and expiry metadata are stored.
No keys, PEM, unredacted kubeadm stdout or kubeconfig.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261112_internal_pki'
down_revision = '20261025_bot_protection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'internal_pki_evidence_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('cluster_id', sa.String(36), sa.ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_name', sa.String(255), nullable=False),
        sa.Column('source_kind', sa.String(50), nullable=False),
        sa.Column('source_version', sa.String(64), nullable=False),
        sa.Column('operator_reference', sa.String(120), nullable=False),
        sa.Column('coverage_state', sa.String(20), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('record_count', sa.Integer(), nullable=False),
    )
    op.create_index('ix_internal_pki_evidence_batches_cluster_id', 'internal_pki_evidence_batches', ['cluster_id'])
    op.create_index(
        'ix_internal_pki_batch_scope',
        'internal_pki_evidence_batches',
        ['cluster_id', 'node_name', 'source_kind', 'collected_at'],
    )
    op.create_table(
        'internal_pki_certificate_inventory',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cluster_id', sa.String(36), sa.ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_name', sa.String(255), nullable=False),
        sa.Column('source_kind', sa.String(50), nullable=False),
        sa.Column('component', sa.String(80), nullable=False),
        sa.Column('kind', sa.String(12), nullable=False),
        sa.Column('issuer', sa.String(120), nullable=True),
        sa.Column('not_before', sa.DateTime(timezone=True), nullable=True),
        sa.Column('not_after', sa.DateTime(timezone=True), nullable=False),
        sa.Column('externally_managed', sa.Boolean(), nullable=True),
        sa.Column(
            'evidence_batch_id', sa.String(36),
            sa.ForeignKey('internal_pki_evidence_batches.id', ondelete='RESTRICT'), nullable=False
        ),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('cluster_id', 'node_name', 'source_kind', 'component', name='uq_internal_pki_source_cert'),
    )
    op.create_index('ix_internal_pki_certificate_inventory_not_after', 'internal_pki_certificate_inventory', ['not_after'])
    op.create_index(
        'ix_internal_pki_certificate_scope',
        'internal_pki_certificate_inventory',
        ['cluster_id', 'node_name', 'source_kind'],
    )


def downgrade() -> None:
    op.drop_index('ix_internal_pki_certificate_scope', table_name='internal_pki_certificate_inventory')
    op.drop_index('ix_internal_pki_certificate_inventory_not_after', table_name='internal_pki_certificate_inventory')
    op.drop_table('internal_pki_certificate_inventory')
    op.drop_index('ix_internal_pki_batch_scope', table_name='internal_pki_evidence_batches')
    op.drop_index('ix_internal_pki_evidence_batches_cluster_id', table_name='internal_pki_evidence_batches')
    op.drop_table('internal_pki_evidence_batches')
