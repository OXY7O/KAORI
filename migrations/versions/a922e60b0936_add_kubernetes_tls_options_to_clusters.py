"""add kubernetes tls options to clusters

Revision ID: a922e60b0936
Revises: f56c0cf05b8b
Create Date: 2026-06-28
"""

import sqlalchemy as sa
from alembic import op

revision = 'a922e60b0936'
down_revision = 'f56c0cf05b8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'clusters',
        sa.Column(
            'kube_verify_ssl',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        'clusters',
        sa.Column(
            'kube_allow_weak_tls',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        'clusters',
        'kube_verify_ssl',
        server_default=None,
    )

    op.alter_column(
        'clusters',
        'kube_allow_weak_tls',
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        'clusters',
        'kube_allow_weak_tls',
    )

    op.drop_column(
        'clusters',
        'kube_verify_ssl',
    )
