"""add user last login metadata

Revision ID: 20260704_user_login_meta
Revises: 20260704_add_auth_login_events
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260704_user_login_meta'
down_revision: Union[str, None] = '20260704_add_auth_login_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('last_login_ip', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('last_auth_source', sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_auth_source')
        batch_op.drop_column('last_login_ip')
        batch_op.drop_column('last_login_at')
