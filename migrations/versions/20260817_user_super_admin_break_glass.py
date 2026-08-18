"""Enforce Local Database ownership for the break-glass super-admin flag.

Revision ID: 20260817_user_break_glass_v1
Revises: 20260817_integration_type_v1
"""

from alembic import op

revision = '20260817_user_break_glass_v1'
down_revision = '20260817_integration_type_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # External identities may keep their normal RBAC role, but the explicit
    # break-glass flag belongs only to Local Database accounts. Clean legacy
    # invalid rows before enforcing the invariant at the database boundary.
    op.execute("UPDATE users SET is_super_admin = false WHERE is_super_admin = true AND auth_source <> 'database'")
    op.create_check_constraint(
        'ck_users_super_admin_local_database',
        'users',
        "NOT is_super_admin OR auth_source = 'database'",
    )


def downgrade() -> None:
    op.drop_constraint('ck_users_super_admin_local_database', 'users', type_='check')
