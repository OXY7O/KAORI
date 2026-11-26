"""Add exact credential issuer administration scope (#5245).

Revision ID: 20261127_issuer_admin_scope
Revises: 20261126_spki_issuer_challenge

No grants, defaults, seed or activation.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261127_issuer_admin_scope'
down_revision = '20261126_spki_issuer_challenge'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('access_scope_policies') as batch:
        batch.add_column(sa.Column('issuer_deployment_ref', sa.String(64), nullable=True))
        batch.drop_constraint('ck_access_scope_policy_level', type_='check')
        batch.drop_constraint('ck_access_scope_policy_exact_target', type_='check')
        batch.create_check_constraint(
            'ck_access_scope_policy_level',
            "scope_level IN ('instance', 'vault_mount', 'automation_credential', 'credential_issuer')",
        )
        batch.create_check_constraint(
            'ck_access_scope_policy_exact_target',
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            " OR (scope_level IN ('vault_mount', 'automation_credential', 'credential_issuer')"
            ' AND provider_namespace IS NOT NULL'
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
        )
        batch.create_check_constraint(
            'ck_access_scope_policy_issuer_target',
            "(scope_level = 'credential_issuer' AND permission_key IN ("
            "'secrets_pki.request_credential_issuer', 'secrets_pki.approve_credential_issuer', "
            "'secrets_pki.revoke_credential_issuer') AND issuer_deployment_ref IS NOT NULL"
            " AND length(issuer_deployment_ref) = 64 AND provider_namespace NOT LIKE '%*%'"
            " AND provider_namespace NOT LIKE '%+%' AND mount NOT LIKE '%+%')"
            " OR (scope_level <> 'credential_issuer' AND permission_key NOT IN ("
            "'secrets_pki.request_credential_issuer', 'secrets_pki.approve_credential_issuer', "
            "'secrets_pki.revoke_credential_issuer') AND issuer_deployment_ref IS NULL)",
        )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(
        sa.text("SELECT COUNT(*) FROM access_scope_policies WHERE scope_level = 'credential_issuer'")
    ).scalar_one()
    if count:
        raise RuntimeError('Credential issuer scope history must be retained before downgrade.')
    with op.batch_alter_table('access_scope_policies') as batch:
        batch.drop_constraint('ck_access_scope_policy_issuer_target', type_='check')
        batch.drop_constraint('ck_access_scope_policy_exact_target', type_='check')
        batch.drop_constraint('ck_access_scope_policy_level', type_='check')
        batch.drop_column('issuer_deployment_ref')
        batch.create_check_constraint(
            'ck_access_scope_policy_level',
            "scope_level IN ('instance', 'vault_mount', 'automation_credential')",
        )
        batch.create_check_constraint(
            'ck_access_scope_policy_exact_target',
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            " OR ((scope_level = 'vault_mount' OR scope_level = 'automation_credential')"
            ' AND provider_namespace IS NOT NULL'
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
        )
