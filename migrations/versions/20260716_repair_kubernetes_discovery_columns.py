"""repair Kubernetes compatibility evidence columns

Revision ID: 20260716_k8s_discovery_repair
Revises: 20260716_profile_names
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_k8s_discovery_repair'
down_revision = '20260716_profile_names'
branch_labels = None
depends_on = None

def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table)}

def upgrade() -> None:
    columns = _columns('clusters')
    if 'kubernetes_lifecycle_status' not in columns:
        op.add_column('clusters', sa.Column('kubernetes_lifecycle_status', sa.String(length=20), nullable=True))
    if 'kubernetes_api_discovery_summary' not in columns:
        op.add_column('clusters', sa.Column('kubernetes_api_discovery_summary', sa.JSON(), nullable=True))

def downgrade() -> None:
    columns = _columns('clusters')
    if 'kubernetes_api_discovery_summary' in columns:
        op.drop_column('clusters', 'kubernetes_api_discovery_summary')
    if 'kubernetes_lifecycle_status' in columns:
        op.drop_column('clusters', 'kubernetes_lifecycle_status')
