"""Add committed Source Control repository collection-generation fencing (#2742).

Revision ID: 20261023_sc_repo_collection
Revises: 20261023_sc_webhook_delivery

No actual GitHub data is seeded and no source evidence is synthesized.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_sc_repo_collection'
down_revision = '20261023_sc_webhook_delivery'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'source_control_repositories',
        sa.Column('default_branch', sa.String(512), nullable=True),
    )
    op.add_column(
        'source_control_repositories',
        sa.Column('visibility', sa.String(16), nullable=True),
    )
    op.create_table(
        'source_control_repository_collection_states',
        sa.Column(
            'installation_id', sa.Integer(),
            sa.ForeignKey('source_control_installations.id', ondelete='RESTRICT'),
            primary_key=True,
        ),
        sa.Column('next_generation', sa.Integer(), nullable=False),
        sa.Column('pending_generation', sa.Integer(), nullable=True),
        sa.Column('committed_generation', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('repository_scope', sa.String(16), nullable=False),
        sa.Column('coverage', sa.String(30), nullable=False),
        sa.Column('observed_count', sa.Integer(), nullable=True),
        sa.Column('last_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(255), nullable=True),
        sa.CheckConstraint('next_generation >= committed_generation',
                           name='ck_sc_collection_generation_order'),
    )
    op.create_index(
        'ix_sc_collection_status', 'source_control_repository_collection_states',
        ['status', 'last_committed_at'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_sc_collection_status', table_name='source_control_repository_collection_states'
    )
    op.drop_table('source_control_repository_collection_states')
    op.drop_column('source_control_repositories', 'visibility')
    op.drop_column('source_control_repositories', 'default_branch')
