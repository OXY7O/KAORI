"""add auth source to users

Revision ID: 195a5f19967b
Revises: 20260703_add_ingress_paths
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '195a5f19967b'
down_revision = '20260703_add_ingress_paths'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'auth_source',
                sa.String(length=50),
                nullable=False,
                server_default='database',
            )
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('auth_source', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('auth_source')
