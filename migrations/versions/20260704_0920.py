"""allow username reuse after soft delete

Revision ID: 20260704_0920
Revises: 20260704_0910
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260704_0920'
down_revision: Union[str, None] = '20260704_0910'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Soft-deleted users remain stored for audit, but their username/email should
    # not block creation of a new active account. PostgreSQL partial unique
    # indexes enforce uniqueness only for rows where deleted_at IS NULL.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('users_username_key', type_='unique')
        batch_op.drop_constraint('users_email_key', type_='unique')

    op.create_index(
        'uq_users_username_active',
        'users',
        ['username'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'uq_users_email_active',
        'users',
        ['email'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_users_email_active', table_name='users')
    op.drop_index('uq_users_username_active', table_name='users')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_unique_constraint('users_email_key', ['email'])
        batch_op.create_unique_constraint('users_username_key', ['username'])
