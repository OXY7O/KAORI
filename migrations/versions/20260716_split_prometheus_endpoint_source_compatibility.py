"""split Prometheus endpoint and source compatibility

Revision ID: 20260716_prom_endpoint_source
Revises: 20260716_prom_detection
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_prom_endpoint_source'
down_revision = '20260716_prom_detection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'prometheus_configs',
        'manual_compatibility_profile',
        new_column_name='source_prometheus_profile',
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )
    op.add_column(
        'prometheus_configs',
        sa.Column('endpoint_product', sa.String(length=32), nullable=True),
    )

    op.execute("""
        UPDATE prometheus_configs
        SET endpoint_product = CASE
            WHEN version_detection_mode = 'manual' THEN 'thanos'
            ELSE 'prometheus'
        END
    """)
    op.execute("""
        UPDATE prometheus_configs
        SET detected_version = NULL,
            compatibility_profile = NULL,
            compatibility_status = 'validation_required',
            readiness_status = 'validation_required',
            query_validation_status = 'validation_required',
            validation_message = 'Compatibility evidence was reset after endpoint and Prometheus source identities were separated.',
            last_validated_at = NULL
        WHERE version_detection_mode = 'manual'
    """)


def downgrade() -> None:
    op.drop_column('prometheus_configs', 'endpoint_product')
    op.alter_column(
        'prometheus_configs',
        'source_prometheus_profile',
        new_column_name='manual_compatibility_profile',
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )
