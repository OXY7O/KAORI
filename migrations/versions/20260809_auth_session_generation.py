"""bind authenticated sessions to local credential generation

Revision ID: 20260809_auth_session_generation
Revises: 20260808_data_lifecycle_ops
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260809_auth_session_generation'
down_revision = '20260808_data_lifecycle_ops'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'auth_session_version',
                sa.Integer(),
                server_default=sa.text('1'),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('auth_session_version')
