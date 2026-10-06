"""move protected secret reveal policy to namespace scope

Revision ID: 20260714_ns_reveal_policy
Revises: 20260714_single_kubeconfig
Create Date: 2026-07-14 18:00:00
"""

from alembic import op
import sqlalchemy as sa

revision: str = '20260714_ns_reveal_policy'
down_revision: str | None = '20260714_single_kubeconfig'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'secret_reveal_namespace_policies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('policy', sa.String(length=32), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'cluster_id',
            'namespace',
            name='uq_secret_reveal_namespace_policy_cluster_namespace',
        ),
    )
    op.create_index(
        'ix_secret_reveal_namespace_policies_cluster_id',
        'secret_reveal_namespace_policies',
        ['cluster_id'],
        unique=False,
    )
    op.create_index(
        'ix_secret_reveal_namespace_policies_namespace',
        'secret_reveal_namespace_policies',
        ['namespace'],
        unique=False,
    )
    op.create_index(
        'ix_secret_reveal_namespace_policies_policy',
        'secret_reveal_namespace_policies',
        ['policy'],
        unique=False,
    )

    # Namespace access is intentionally default-deny. Existing cluster-wide
    # policies are not expanded automatically because that would grant reveal
    # access to every namespace after the migration.
    op.drop_column('clusters', 'secret_reveal_policy')


def downgrade() -> None:
    op.add_column(
        'clusters',
        sa.Column(
            'secret_reveal_policy',
            sa.String(length=32),
            nullable=False,
            server_default='disabled',
        ),
    )
    op.alter_column('clusters', 'secret_reveal_policy', server_default=None)
    op.drop_index(
        'ix_secret_reveal_namespace_policies_policy',
        table_name='secret_reveal_namespace_policies',
    )
    op.drop_index(
        'ix_secret_reveal_namespace_policies_namespace',
        table_name='secret_reveal_namespace_policies',
    )
    op.drop_index(
        'ix_secret_reveal_namespace_policies_cluster_id',
        table_name='secret_reveal_namespace_policies',
    )
    op.drop_table('secret_reveal_namespace_policies')
