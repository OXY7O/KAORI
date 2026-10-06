"""promote object storage consumer metrics profile

Revision ID: 20260814_obj_metrics_profile
Revises: 20260813_obj_quota_diag
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260814_obj_metrics_profile'
down_revision = '20260813_obj_quota_diag'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_profile = 'object-storage-metrics-v1',
                validation_status = 'validation_required',
                validation_evidence = NULL,
                validation_message = 'Object Storage metrics contract changed. Rerun Prometheus Full Validation or Validate this consumer binding.',
                last_validated_at = NULL
            WHERE asset_type = 'object_storage_system'
              AND validation_profile = 'minio-metrics-2024-v1'
              AND integration_instance_id IN (
                  SELECT id FROM integration_instances WHERE provider_type = 'prometheus'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_profile = 'minio-metrics-2024-v1',
                validation_status = 'validation_required',
                validation_evidence = NULL,
                validation_message = 'Consumer profile changed by downgrade. Rerun validation before operational use.',
                last_validated_at = NULL
            WHERE asset_type = 'object_storage_system'
              AND validation_profile = 'object-storage-metrics-v1'
              AND integration_instance_id IN (
                  SELECT id FROM integration_instances WHERE provider_type = 'prometheus'
              )
            """
        )
    )
