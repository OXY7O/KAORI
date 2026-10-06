"""resolver production readiness and controlled rollout

Revision ID: 20260723_resolver_readiness
Revises: 20260723_resolver_controls
"""

from alembic import op
import sqlalchemy as sa

revision = '20260723_resolver_readiness'
down_revision = '20260723_resolver_controls'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'resolver_production_readiness',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('action_key', sa.String(length=255), nullable=False),
        sa.Column('rollout_stage', sa.String(length=32), nullable=False, server_default='disabled'),
        sa.Column('validation_results_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('evidence_hash', sa.String(length=64), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rollout_stage IN ('disabled', 'shadow', 'non_production', 'canary', 'production')",
            name='ck_resolver_readiness_stage',
        ),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['validated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('cluster_id', 'action_key', name='uq_resolver_readiness_cluster_action'),
    )
    op.create_index('ix_resolver_production_readiness_cluster_id', 'resolver_production_readiness', ['cluster_id'])
    op.create_index('ix_resolver_production_readiness_action_key', 'resolver_production_readiness', ['action_key'])
    op.create_index(
        'ix_resolver_production_readiness_rollout_stage', 'resolver_production_readiness', ['rollout_stage']
    )


def downgrade() -> None:
    op.drop_table('resolver_production_readiness')
