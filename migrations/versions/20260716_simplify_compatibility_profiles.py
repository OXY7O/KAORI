"""Simplify Kubernetes, Prometheus, and Alertmanager compatibility profiles.

Revision ID: 20260716_profile_names
Revises: 20260716_split_prom_compat
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_profile_names'
down_revision = '20260716_prom_endpoint_source'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('prometheus_configs') as batch:
        batch.alter_column('source_prometheus_profile', new_column_name='source_prometheus_major', existing_type=sa.String(length=100), type_=sa.String(length=8), existing_nullable=True)
    with op.batch_alter_table('alertmanager_configs') as batch:
        batch.add_column(sa.Column('capability_profile', sa.String(length=100), nullable=True))
    with op.batch_alter_table('clusters') as batch:
        batch.add_column(sa.Column('kubernetes_lifecycle_status', sa.String(length=40), nullable=True))

    op.execute("UPDATE prometheus_configs SET source_prometheus_major = CASE source_prometheus_major WHEN 'prometheus-v2-kubernetes-v1' THEN '2' WHEN 'prometheus-v3-kubernetes-v1' THEN '3' WHEN 'prometheus-http-v2' THEN '2' WHEN 'prometheus-http-v3' THEN '3' ELSE source_prometheus_major END")
    op.execute("UPDATE prometheus_configs SET compatibility_profile = CASE compatibility_profile WHEN 'prometheus-v2-kubernetes-v1' THEN 'prometheus-http-v2' WHEN 'prometheus-v3-kubernetes-v1' THEN 'prometheus-http-v3' ELSE compatibility_profile END")
    op.execute("UPDATE prometheus_configs SET query_profile = 'promql-kubernetes-v1' WHERE query_profile IN ('prometheus-kubernetes-v1', 'promql-kubernetes-v2', 'promql-kubernetes-v3')")
    op.execute("UPDATE alertmanager_configs SET compatibility_profile = CASE compatibility_profile WHEN 'alertmanager-v2-legacy' THEN 'alertmanager-api-v2-legacy' WHEN 'alertmanager-v2-current' THEN 'alertmanager-api-v2-current' ELSE compatibility_profile END")
    op.execute("UPDATE alertmanager_configs SET capability_profile = 'alert-management-v1'")
    op.execute("UPDATE clusters SET kubernetes_compatibility_profile = 'kubernetes-api-v1' WHERE kubernetes_compatibility_profile IS NOT NULL")


def downgrade() -> None:
    op.execute("UPDATE prometheus_configs SET source_prometheus_major = CASE source_prometheus_major WHEN '2' THEN 'prometheus-v2-kubernetes-v1' WHEN '3' THEN 'prometheus-v3-kubernetes-v1' ELSE source_prometheus_major END")
    op.execute("UPDATE prometheus_configs SET compatibility_profile = CASE compatibility_profile WHEN 'prometheus-http-v2' THEN 'prometheus-v2-kubernetes-v1' WHEN 'prometheus-http-v3' THEN 'prometheus-v3-kubernetes-v1' ELSE compatibility_profile END")
    op.execute("UPDATE alertmanager_configs SET compatibility_profile = CASE compatibility_profile WHEN 'alertmanager-api-v2-legacy' THEN 'alertmanager-v2-legacy' WHEN 'alertmanager-api-v2-current' THEN 'alertmanager-v2-current' ELSE compatibility_profile END")
    with op.batch_alter_table('clusters') as batch:
        batch.drop_column('kubernetes_lifecycle_status')
    with op.batch_alter_table('alertmanager_configs') as batch:
        batch.drop_column('capability_profile')
    with op.batch_alter_table('prometheus_configs') as batch:
        batch.alter_column('source_prometheus_major', new_column_name='source_prometheus_profile', existing_type=sa.String(length=8), type_=sa.String(length=100), existing_nullable=True)
