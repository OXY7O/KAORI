"""add protected kubernetes secret reveal

Revision ID: 20260714_secret_reveal
Revises: 20260713_archive_retention
Create Date: 2026-07-14 14:00:00
"""

from alembic import op
import sqlalchemy as sa

revision: str = '20260714_secret_reveal'
down_revision: str | None = '20260713_archive_retention'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'clusters',
        sa.Column('secret_reveal_policy', sa.String(length=32), nullable=False, server_default='disabled'),
    )
    op.add_column('clusters', sa.Column('secret_reveal_kubeconfig', sa.Text(), nullable=True))
    op.add_column(
        'clusters',
        sa.Column('secret_reveal_encryption_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'clusters',
        sa.Column('secret_reveal_audit_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('clusters', 'secret_reveal_policy', server_default=None)
    op.alter_column('clusters', 'secret_reveal_encryption_verified', server_default=None)
    op.alter_column('clusters', 'secret_reveal_audit_verified', server_default=None)

    op.create_table(
        'secret_reveal_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('configuration_inventory_id', sa.Integer(), nullable=True),
        sa.Column('cluster_id', sa.String(length=36), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('secret_name', sa.String(length=255), nullable=False),
        sa.Column('secret_type', sa.String(length=255), nullable=False),
        sa.Column('key_name', sa.String(length=255), nullable=False),
        sa.Column('policy', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('ticket_reference', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('requester_user_id', sa.Integer(), nullable=False),
        sa.Column('approver_user_id', sa.Integer(), nullable=True),
        sa.Column('requester_ip', sa.String(length=100), nullable=True),
        sa.Column('decision_note', sa.String(length=500), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revealed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['configuration_inventory_id'], ['configuration_inventory.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    for column in (
        'configuration_inventory_id',
        'cluster_id',
        'namespace',
        'secret_name',
        'ticket_reference',
        'status',
        'requester_user_id',
        'approver_user_id',
        'requested_at',
        'expires_at',
    ):
        op.create_index(f'ix_secret_reveal_requests_{column}', 'secret_reveal_requests', [column], unique=False)


def downgrade() -> None:
    for column in reversed(
        (
            'configuration_inventory_id',
            'cluster_id',
            'namespace',
            'secret_name',
            'ticket_reference',
            'status',
            'requester_user_id',
            'approver_user_id',
            'requested_at',
            'expires_at',
        )
    ):
        op.drop_index(f'ix_secret_reveal_requests_{column}', table_name='secret_reveal_requests')
    op.drop_table('secret_reveal_requests')
    op.drop_column('clusters', 'secret_reveal_audit_verified')
    op.drop_column('clusters', 'secret_reveal_encryption_verified')
    op.drop_column('clusters', 'secret_reveal_kubeconfig')
    op.drop_column('clusters', 'secret_reveal_policy')
