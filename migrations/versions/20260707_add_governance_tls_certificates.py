"""add governance tls certificates

Revision ID: 20260707_tls_governance
Revises: 20260706_add_node_inventory_addresses
Create Date: 2026-07-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260707_tls_governance'
down_revision = '20260706_node_addresses'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tls_certificate_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('secret_name', sa.String(length=255), nullable=False),
        sa.Column('secret_type', sa.String(length=100), nullable=True),
        sa.Column('common_name', sa.String(length=255), nullable=True),
        sa.Column('issuer', sa.String(length=512), nullable=True),
        sa.Column('serial_number', sa.String(length=128), nullable=True),
        sa.Column('fingerprint_sha256', sa.String(length=128), nullable=True),
        sa.Column('dns_names', sa.JSON(), nullable=False),
        sa.Column('ingress_hosts', sa.JSON(), nullable=False),
        sa.Column('used_by', sa.JSON(), nullable=False),
        sa.Column('not_before', sa.DateTime(timezone=True), nullable=True),
        sa.Column('not_after', sa.DateTime(timezone=True), nullable=True),
        sa.Column('days_remaining', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('risk_level', sa.String(length=50), nullable=False),
        sa.Column('parse_error', sa.Text(), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster_id', 'namespace', 'secret_name', name='uq_tls_certificate_inventory_secret'),
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_cluster_id'), 'tls_certificate_inventory', ['cluster_id'], unique=False
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_collected_at'), 'tls_certificate_inventory', ['collected_at'], unique=False
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_fingerprint_sha256'),
        'tls_certificate_inventory',
        ['fingerprint_sha256'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_namespace'), 'tls_certificate_inventory', ['namespace'], unique=False
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_not_after'), 'tls_certificate_inventory', ['not_after'], unique=False
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_risk_level'), 'tls_certificate_inventory', ['risk_level'], unique=False
    )
    op.create_index(
        op.f('ix_tls_certificate_inventory_secret_name'), 'tls_certificate_inventory', ['secret_name'], unique=False
    )
    op.create_index(op.f('ix_tls_certificate_inventory_status'), 'tls_certificate_inventory', ['status'], unique=False)

    op.create_table(
        'tls_certificate_update_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('secret_name', sa.String(length=255), nullable=False),
        sa.Column('old_fingerprint_sha256', sa.String(length=128), nullable=True),
        sa.Column('new_fingerprint_sha256', sa.String(length=128), nullable=True),
        sa.Column('old_not_after', sa.DateTime(timezone=True), nullable=True),
        sa.Column('new_not_after', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('bulk_job_id', sa.String(length=64), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_tls_certificate_update_events_bulk_job_id'),
        'tls_certificate_update_events',
        ['bulk_job_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tls_certificate_update_events_cluster_id'),
        'tls_certificate_update_events',
        ['cluster_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tls_certificate_update_events_created_at'),
        'tls_certificate_update_events',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tls_certificate_update_events_namespace'), 'tls_certificate_update_events', ['namespace'], unique=False
    )
    op.create_index(
        op.f('ix_tls_certificate_update_events_secret_name'),
        'tls_certificate_update_events',
        ['secret_name'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tls_certificate_update_events_status'), 'tls_certificate_update_events', ['status'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_tls_certificate_update_events_status'), table_name='tls_certificate_update_events')
    op.drop_index(op.f('ix_tls_certificate_update_events_secret_name'), table_name='tls_certificate_update_events')
    op.drop_index(op.f('ix_tls_certificate_update_events_namespace'), table_name='tls_certificate_update_events')
    op.drop_index(op.f('ix_tls_certificate_update_events_created_at'), table_name='tls_certificate_update_events')
    op.drop_index(op.f('ix_tls_certificate_update_events_cluster_id'), table_name='tls_certificate_update_events')
    op.drop_index(op.f('ix_tls_certificate_update_events_bulk_job_id'), table_name='tls_certificate_update_events')
    op.drop_table('tls_certificate_update_events')

    op.drop_index(op.f('ix_tls_certificate_inventory_status'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_secret_name'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_risk_level'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_not_after'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_namespace'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_fingerprint_sha256'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_collected_at'), table_name='tls_certificate_inventory')
    op.drop_index(op.f('ix_tls_certificate_inventory_cluster_id'), table_name='tls_certificate_inventory')
    op.drop_table('tls_certificate_inventory')
