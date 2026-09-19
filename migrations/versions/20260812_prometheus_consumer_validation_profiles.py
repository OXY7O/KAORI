"""add consumer validation profile evidence to integration bindings

Revision ID: 20260812_prom_consumer_profiles
Revises: 20260812_minio_object_storage
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260812_prom_consumer_profiles'
down_revision = '20260812_minio_object_storage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'integration_bindings',
        sa.Column('validation_profile', sa.String(length=120), nullable=True),
    )
    op.add_column(
        'integration_bindings',
        sa.Column('validation_evidence', sa.JSON(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_profile = 'kubernetes-metrics-v1'
            WHERE asset_type = 'kubernetes_cluster'
              AND integration_instance_id IN (
                  SELECT id FROM integration_instances WHERE provider_type = 'prometheus'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_profile = 'minio-metrics-2024-v1'
            WHERE asset_type = 'object_storage_system'
              AND integration_instance_id IN (
                  SELECT id FROM integration_instances WHERE provider_type = 'prometheus'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_status = 'validation_required',
                validation_evidence = NULL,
                validation_message = 'Consumer validation model changed. Run Prometheus Full Validation to refresh this asset binding.',
                last_validated_at = NULL
            WHERE integration_instance_id IN (
                SELECT id FROM integration_instances WHERE provider_type = 'prometheus'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE integration_instances
            SET readiness_status = 'validation_required'
            WHERE provider_type = 'prometheus'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE prometheus_instances
            SET query_profile = 'prometheus-core-v1',
                query_validation_status = 'validation_required',
                query_validation_summary = NULL,
                retention_validation_summary = NULL,
                capability_profile = NULL,
                capabilities = NULL,
                module_readiness = NULL,
                validation_message = 'Consumer validation model changed. Run Full Validation to establish Prometheus core readiness and refresh bound consumers.',
                last_validated_at = NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE integration_instances
            SET readiness_status = 'validation_required'
            WHERE provider_type = 'prometheus'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE prometheus_instances
            SET query_profile = NULL,
                query_validation_status = 'validation_required',
                query_validation_summary = NULL,
                retention_validation_summary = NULL,
                capability_profile = NULL,
                capabilities = NULL,
                module_readiness = NULL,
                validation_message = 'Validation contract changed by downgrade. Run Full Validation before operational use.',
                last_validated_at = NULL
            """
        )
    )
    op.drop_column('integration_bindings', 'validation_evidence')
    op.drop_column('integration_bindings', 'validation_profile')
