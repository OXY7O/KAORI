"""resolver registry bootstrap and deployment policy

Revision ID: 20260723_resolver_registry
Revises: 20260723_candidate_review
"""

from alembic import op
import sqlalchemy as sa

revision = '20260723_resolver_registry'
down_revision = '20260723_candidate_review'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'resolver_deployment_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('action_key', sa.String(length=255), nullable=False),
        sa.Column('lifecycle_status', sa.String(length=20), nullable=False, server_default='disabled'),
        sa.Column('allowed_namespaces_json', sa.JSON(), nullable=False),
        sa.Column('required_registry_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("lifecycle_status IN ('active', 'disabled')", name='ck_resolver_policy_lifecycle'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('cluster_id', 'action_key', name='uq_resolver_policy_cluster_action'),
    )
    op.create_index(
        'ix_resolver_policy_cluster_status', 'resolver_deployment_policies', ['cluster_id', 'lifecycle_status']
    )
    op.create_index('ix_resolver_deployment_policies_action_key', 'resolver_deployment_policies', ['action_key'])


def downgrade() -> None:
    op.drop_table('resolver_deployment_policies')
