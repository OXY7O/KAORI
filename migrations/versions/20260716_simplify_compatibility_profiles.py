"""simplify compatibility profiles and add Kubernetes API discovery evidence

Revision ID: 20260716_profile_names
Revises: 20260716_prom_endpoint_source
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_profile_names'
down_revision = '20260716_prom_endpoint_source'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the old width while legacy identifiers are normalized.
    op.alter_column(
        'prometheus_configs',
        'source_prometheus_profile',
        new_column_name='source_prometheus_major',
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )
    op.execute("""
        UPDATE prometheus_configs
        SET source_prometheus_major = CASE
            WHEN source_prometheus_major IN ('2', 'prometheus-http-v2', 'prometheus-v2-kubernetes-v1') THEN '2'
            WHEN source_prometheus_major IN ('3', 'prometheus-http-v3', 'prometheus-v3-kubernetes-v1') THEN '3'
            ELSE NULL
        END
    """)
    op.alter_column(
        'prometheus_configs',
        'source_prometheus_major',
        existing_type=sa.String(length=100),
        type_=sa.String(length=8),
        existing_nullable=True,
    )
    op.execute("""
        UPDATE prometheus_configs
        SET compatibility_profile = CASE
            WHEN compatibility_profile = 'prometheus-v2-kubernetes-v1' THEN 'prometheus-http-v2'
            WHEN compatibility_profile = 'prometheus-v3-kubernetes-v1' THEN 'prometheus-http-v3'
            ELSE compatibility_profile
        END,
        query_profile = CASE
            WHEN query_profile IN ('promql-kubernetes-v2', 'promql-kubernetes-v3', 'prometheus-kubernetes-v1')
                THEN 'promql-kubernetes-v1'
            ELSE query_profile
        END
    """)
    op.execute("""
        UPDATE alertmanager_configs
        SET compatibility_profile = CASE
            WHEN compatibility_profile = 'alertmanager-v2-legacy' THEN 'alertmanager-api-v2-legacy'
            WHEN compatibility_profile = 'alertmanager-v2-current' THEN 'alertmanager-api-v2-current'
            ELSE compatibility_profile
        END
    """)
    op.add_column('alertmanager_configs', sa.Column('capability_profile', sa.String(length=100), nullable=True))
    op.execute("UPDATE alertmanager_configs SET capability_profile = 'alert-management-v1' WHERE endpoint IS NOT NULL")

    op.add_column('clusters', sa.Column('kubernetes_lifecycle_status', sa.String(length=20), nullable=True))
    op.add_column('clusters', sa.Column('kubernetes_api_discovery_summary', sa.JSON(), nullable=True))
    op.execute("UPDATE clusters SET kubernetes_compatibility_profile = 'kubernetes-api-v1' WHERE kubernetes_version IS NOT NULL")


def downgrade() -> None:
    op.drop_column('clusters', 'kubernetes_api_discovery_summary')
    op.drop_column('clusters', 'kubernetes_lifecycle_status')
    op.drop_column('alertmanager_configs', 'capability_profile')
    op.alter_column('prometheus_configs', 'source_prometheus_major', existing_type=sa.String(length=8), type_=sa.String(length=100), existing_nullable=True)
    op.execute("""
        UPDATE prometheus_configs
        SET source_prometheus_major = CASE
            WHEN source_prometheus_major = '2' THEN 'prometheus-v2-kubernetes-v1'
            WHEN source_prometheus_major = '3' THEN 'prometheus-v3-kubernetes-v1'
            ELSE NULL
        END
    """)
    op.alter_column('prometheus_configs', 'source_prometheus_major', new_column_name='source_prometheus_profile', existing_type=sa.String(length=100), existing_nullable=True)
