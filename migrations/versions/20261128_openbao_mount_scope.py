"""Add local OpenBao metadata-only exact mount scope (#5204)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_openbao_mount_scope'
down_revision = '20261128_openbao_connection'
branch_labels = None
depends_on = None


def _replace_checks(*, include_openbao: bool) -> None:
    mounts = "'vault_mount', 'automation_credential', 'credential_issuer'"
    if include_openbao:
        mounts = "'vault_mount', 'openbao_mount', 'automation_credential', 'credential_issuer'"
    with op.batch_alter_table('access_scope_policies') as batch:
        batch.drop_constraint('ck_access_scope_policy_level', type_='check')
        batch.drop_constraint('ck_access_scope_policy_exact_target', type_='check')
        if not include_openbao:
            batch.drop_constraint('ck_access_scope_policy_openbao_target', type_='check')
        batch.create_check_constraint(
            'ck_access_scope_policy_level',
            f"scope_level IN ('instance', {mounts})",
        )
        batch.create_check_constraint(
            'ck_access_scope_policy_exact_target',
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            f" OR (scope_level IN ({mounts})"
            ' AND provider_namespace IS NOT NULL'
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
        )
        if include_openbao:
            batch.create_check_constraint(
                'ck_access_scope_policy_openbao_target',
                "scope_level <> 'openbao_mount' OR (permission_key = 'secrets_pki.view'"
                " AND provider_namespace = '' AND mount NOT LIKE '%+%')",
            )


def upgrade() -> None:
    _replace_checks(include_openbao=True)


def downgrade() -> None:
    count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM access_scope_policies WHERE scope_level = 'openbao_mount'")
    ).scalar_one()
    if count:
        raise RuntimeError('OpenBao scope policy history must be retained before downgrade.')
    _replace_checks(include_openbao=False)
