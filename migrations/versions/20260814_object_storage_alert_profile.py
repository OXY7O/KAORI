"""promote object storage alert consumer profile

Revision ID: 20260814_obj_alert_profile
Revises: 20260814_obj_forecast
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260814_obj_alert_profile'
down_revision = '20260814_obj_forecast'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_profile = 'object-storage-alerts-v1',
                validation_status = 'validation_required',
                validation_evidence = NULL,
                validation_message = 'Object Storage alert consumer profile changed. Rerun Alertmanager Full Validation or Validate this consumer binding.',
                last_validated_at = NULL
            WHERE asset_type = 'object_storage_system'
              AND validation_profile = 'minio-alerts-v1'
              AND integration_instance_id IN (
                  SELECT id FROM integration_instances WHERE provider_type = 'alertmanager'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings
            SET validation_profile = 'minio-alerts-v1',
                validation_status = 'validation_required',
                validation_evidence = NULL,
                validation_message = 'Alert consumer profile changed by downgrade. Rerun validation before operational use.',
                last_validated_at = NULL
            WHERE asset_type = 'object_storage_system'
              AND validation_profile = 'object-storage-alerts-v1'
              AND integration_instance_id IN (
                  SELECT id FROM integration_instances WHERE provider_type = 'alertmanager'
              )
            """
        )
    )
