"""introduce standalone Prometheus runtimes and Kubernetes bindings

Revision ID: 20260718_prom_instances
Revises: 20260718_prom_runtime
"""
from __future__ import annotations

from datetime import UTC, datetime
import sqlalchemy as sa
from alembic import op

revision = '20260718_prom_instances'
down_revision = '20260718_prom_runtime'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prometheus_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(160), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('auth_type', sa.String(30), nullable=False, server_default='none'),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('bearer_token', sa.Text(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('version_detection_mode', sa.String(20), nullable=False, server_default='automatic'),
        sa.Column('endpoint_product', sa.String(32), nullable=True),
        sa.Column('source_prometheus_major', sa.String(8), nullable=True),
        sa.Column('detected_version', sa.String(64), nullable=True),
        sa.Column('compatibility_status', sa.String(40), nullable=True),
        sa.Column('compatibility_profile', sa.String(100), nullable=True),
        sa.Column('readiness_status', sa.String(40), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('query_profile', sa.String(100), nullable=True),
        sa.Column('query_validation_status', sa.String(40), nullable=True),
        sa.Column('query_validation_summary', sa.JSON(), nullable=True),
        sa.Column('retention_validation_summary', sa.JSON(), nullable=True),
        sa.Column('capability_profile', sa.String(100), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('module_readiness', sa.JSON(), nullable=True),
        sa.Column('last_status', sa.String(40), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'prometheus_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('prometheus_instance_id', sa.Integer(), sa.ForeignKey('prometheus_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scope_type', sa.String(50), nullable=False),
        sa.Column('scope_key', sa.String(255), nullable=False),
        sa.Column('binding_role', sa.String(30), nullable=False, server_default='primary'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('prometheus_instance_id', 'scope_type', 'scope_key', name='uq_prometheus_binding_instance_scope'),
    )
    op.create_index('ix_prometheus_bindings_scope', 'prometheus_bindings', ['scope_type', 'scope_key', 'enabled'])

    connection = op.get_bind()
    rows = connection.execute(sa.text('SELECT pc.*, c.name AS cluster_name FROM prometheus_configs pc JOIN clusters c ON c.id = pc.cluster_id ORDER BY pc.id')).mappings().all()
    now = datetime.now(UTC)
    for row in rows:
        result = connection.execute(sa.text('''
            INSERT INTO prometheus_instances (
                name, endpoint, auth_type, username, password, bearer_token, timeout, verify_ssl, enabled,
                version_detection_mode, endpoint_product, source_prometheus_major, detected_version,
                compatibility_status, compatibility_profile, readiness_status, validation_message,
                last_validated_at, query_profile, query_validation_status, query_validation_summary,
                retention_validation_summary, capability_profile, capabilities, module_readiness,
                last_status, last_error, last_response_time_ms, last_checked_at, created_at, updated_at
            ) VALUES (
                :name, :endpoint, :auth_type, :username, :password, :bearer_token, :timeout, :verify_ssl, true,
                :version_detection_mode, :endpoint_product, :source_prometheus_major, :detected_version,
                :compatibility_status, :compatibility_profile, :readiness_status, :validation_message,
                :last_validated_at, :query_profile, :query_validation_status, :query_validation_summary,
                :retention_validation_summary, :capability_profile, :capabilities, :module_readiness,
                :last_status, :last_error, :last_response_time_ms, :last_checked_at, :created_at, :updated_at
            ) RETURNING id
        '''), {**row, 'name': f"{row['cluster_name']} Prometheus", 'created_at': row.get('created_at') or now, 'updated_at': row.get('updated_at') or now}).scalar_one()
        connection.execute(sa.text('''INSERT INTO prometheus_bindings
            (prometheus_instance_id, scope_type, scope_key, binding_role, priority, enabled, created_at, updated_at)
            VALUES (:instance_id, 'kubernetes_cluster', :cluster_id, 'primary', 100, true, :now, :now)
        '''), {'instance_id': result, 'cluster_id': row['cluster_id'], 'now': now})


def downgrade() -> None:
    op.drop_index('ix_prometheus_bindings_scope', table_name='prometheus_bindings')
    op.drop_table('prometheus_bindings')
    op.drop_table('prometheus_instances')
