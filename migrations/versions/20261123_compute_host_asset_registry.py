"""Register non-production provider-neutral Compute Host assets (#5161).

Revision ID: 20261123_compute_host
Revises: 20261112_internal_pki

No host is seeded, no SSH credentials are stored and no provider call or
infrastructure mutation is activated by this schema migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261123_compute_host'
down_revision = '20261112_internal_pki'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'compute_host_assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('asset_key', sa.String(96), nullable=False),
        sa.Column('name', sa.String(180), nullable=False),
        sa.Column('site_key', sa.String(64), nullable=False),
        sa.Column('environment', sa.String(40), nullable=False),
        sa.Column('management_ipv4', sa.String(45), nullable=False),
        sa.Column('ssh_port', sa.Integer(), nullable=False),
        sa.Column(
            'registered_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('asset_key', name='uq_compute_host_asset_key'),
        sa.UniqueConstraint(
            'site_key',
            'environment',
            'management_ipv4',
            name='uq_compute_host_site_environment_address',
        ),
        sa.CheckConstraint('ssh_port BETWEEN 1 AND 65535', name='ck_compute_host_ssh_port'),
        sa.CheckConstraint(
            "environment IN ('development', 'testing', 'staging', 'laboratory',"
            " 'sandbox', 'proof_of_concept', 'non_production')",
            name='ck_compute_host_non_production',
        ),
    )
    op.create_index('ix_compute_host_scope', 'compute_host_assets', ['site_key', 'environment', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_compute_host_scope', table_name='compute_host_assets')
    op.drop_table('compute_host_assets')
