"""rbac auth polish

Revision ID: 20260704_0910
Revises: 20260704_0900
Create Date: 2026-07-04 09:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260704_0910'
down_revision = '20260704_0900'
branch_labels = None
depends_on = None


RESET_PERMISSION_KEY = 'users.reset_password'


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (key, module, action, description, created_at)
        VALUES (
            'users.reset_password',
            'users',
            'reset_password',
            'Reset passwords for database-managed user accounts.',
            NOW()
        )
        ON CONFLICT (key) DO UPDATE SET
            module = EXCLUDED.module,
            action = EXCLUDED.action,
            description = EXCLUDED.description
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT roles.id, permissions.id, NOW()
        FROM roles
        JOIN permissions ON permissions.key = 'users.reset_password'
        WHERE roles.name = 'admin'
        ON CONFLICT ON CONSTRAINT uq_role_permission DO NOTHING
        """
    )

    op.execute("UPDATE users SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE users SET updated_at = NOW() WHERE updated_at IS NULL")

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        USING permissions
        WHERE role_permissions.permission_id = permissions.id
          AND permissions.key = 'users.reset_password'
        """
    )
    op.execute("DELETE FROM permissions WHERE key = 'users.reset_password'")

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
