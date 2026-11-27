"""Add isolated OpenBao provider connections for local UAT (#5203)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_openbao_connection'
down_revision = '20261127_issuer_admin_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'openbao_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(), sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False, unique=True),
        sa.Column('ownership', sa.String(16), nullable=False),
        sa.Column('internal_slot', sa.String(16), nullable=True, unique=True),
        sa.Column('endpoint', sa.String(500), nullable=False, unique=True),
        sa.Column('cluster_id', sa.String(36), nullable=False, unique=True),
        sa.Column('auth_mount', sa.String(160), nullable=False),
        sa.Column('role_id', sa.String(255), nullable=False),
        sa.Column('secret_id', sa.Text(), nullable=False),
        sa.Column('detected_version', sa.String(64)),
        sa.Column('last_validated_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("ownership IN ('internal', 'external')", name='ck_openbao_ownership'),
        sa.CheckConstraint(
            "(ownership = 'internal' AND internal_slot IS NOT NULL AND internal_slot = 'bundled') OR "
            "(ownership = 'external' AND internal_slot IS NULL)",
            name='ck_openbao_internal_slot',
        ),
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM openbao_instances')).scalar_one()
    if count:
        raise RuntimeError('OpenBao connections and evidence must be retained before downgrade.')
    op.drop_table('openbao_instances')
