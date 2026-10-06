"""remove deprecated MinIO owner self-binding

Revision ID: 20260812_minio_owner_cleanup
Revises: 20260812_prom_consumer_profiles
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260812_minio_owner_cleanup'
down_revision = '20260812_prom_consumer_profiles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MinIO owns ObjectStorageSystem through MinioInstance.object_storage_system_id.
    # The old MinIO→object_storage_system IntegrationBinding duplicated that
    # ownership and incorrectly surfaced as a consumer binding. Consumer bindings
    # are reserved for reusable sources such as Prometheus and Alertmanager.
    op.execute(
        sa.text(
            """
            DELETE FROM integration_bindings
            WHERE asset_type = 'object_storage_system'
              AND EXISTS (
                  SELECT 1
                  FROM minio_instances mi
                  JOIN integration_instances ii
                    ON ii.id = mi.integration_instance_id
                  WHERE ii.provider_type = 'minio'
                    AND ii.id = integration_bindings.integration_instance_id
                    AND mi.object_storage_system_id = integration_bindings.asset_key
              )
            """
        )
    )


def downgrade() -> None:
    # This data cleanup is intentionally irreversible. Restoring the deprecated
    # owner self-binding would recreate a relationship that current code no longer
    # treats as a consumer binding.
    pass
