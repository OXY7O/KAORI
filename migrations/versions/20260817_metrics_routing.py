"""Separate Prometheus and Thanos source identity and add metrics routing policy.

Revision ID: 20260817_metrics_routing
Revises: 20260817_lifecycle_policy_seed
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '20260817_metrics_routing'
down_revision = '20260817_lifecycle_policy_seed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    prometheus_columns = {column['name'] for column in inspector.get_columns('prometheus_instances')}
    binding_columns = {column['name'] for column in inspector.get_columns('integration_bindings')}

    if 'source_type' not in prometheus_columns:
        op.add_column(
            'prometheus_instances',
            sa.Column('source_type', sa.String(length=20), nullable=False, server_default='prometheus'),
        )
        op.execute(
            sa.text(
                "UPDATE prometheus_instances SET source_type = 'thanos' "
                "WHERE endpoint_product = 'thanos' OR version_detection_mode = 'manual'"
            )
        )

    # Keep the canonical IntegrationInstance identity explicit so the taxonomy-owned
    # Observability registry can distinguish Prometheus from Thanos Query without
    # provider-specific N+1 lookups.
    if bind.dialect.name == 'postgresql':
        op.execute(
            sa.text(
                'UPDATE integration_instances AS ii '
                "SET metadata_json = (COALESCE(ii.metadata_json::jsonb, '{}'::jsonb) "
                "|| jsonb_build_object('metrics_source_type', pi.source_type))::json "
                'FROM prometheus_instances AS pi '
                'WHERE pi.integration_instance_id = ii.id'
            )
        )

    if 'routing_policy' not in binding_columns:
        op.add_column('integration_bindings', sa.Column('routing_policy', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    binding_columns = {column['name'] for column in inspector.get_columns('integration_bindings')}
    prometheus_columns = {column['name'] for column in inspector.get_columns('prometheus_instances')}

    if 'routing_policy' in binding_columns:
        op.drop_column('integration_bindings', 'routing_policy')
    if 'source_type' in prometheus_columns:
        op.drop_column('prometheus_instances', 'source_type')
