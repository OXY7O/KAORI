"""Add inactive exact automation credential scope selector (#5184).

Revision ID: 20261124_auto_cred_scope
Revises: 20261124_auto_host_access

Storage only: no grants, backfill, provider access or execution.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261124_auto_cred_scope'
down_revision = '20261124_auto_host_access'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('access_scope_policies') as batch:
        batch.drop_constraint('ck_access_scope_policy_level', type_='check')
        batch.drop_constraint('ck_access_scope_policy_exact_target', type_='check')
        batch.create_check_constraint(
            'ck_access_scope_policy_level',
            "scope_level IN ('instance', 'vault_mount', 'automation_credential')",
        )
        batch.create_check_constraint(
            'ck_access_scope_policy_exact_target',
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            " OR ((scope_level = 'vault_mount' OR scope_level = 'automation_credential')"
            " AND provider_namespace IS NOT NULL"
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
        )
        batch.create_check_constraint(
            'ck_access_scope_policy_credential_permission',
            "(scope_level = 'automation_credential' AND permission_key = 'secrets_pki.use_automation_credential')"
            " OR (scope_level <> 'automation_credential' AND permission_key <> 'secrets_pki.use_automation_credential')",
        )
    op.create_table(
        'access_automation_credential_targets',
        sa.Column(
            'policy_id', sa.String(36), sa.ForeignKey('access_scope_policies.id', ondelete='RESTRICT'), primary_key=True
        ),
        sa.Column(
            'ansible_connection_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'assignment_id',
            sa.Integer(),
            sa.ForeignKey('automation_inventory_assignments.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'host_id', sa.String(36), sa.ForeignKey('automation_host_assets.id', ondelete='RESTRICT'), nullable=False
        ),
        sa.Column('host_revision', sa.String(64), nullable=False),
        sa.Column('reference_fingerprint', sa.String(64), nullable=False),
        sa.Column(
            'secret_identity_id',
            sa.String(36),
            sa.ForeignKey('secrets_pki_secret_identities.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'secret_representation_id',
            sa.Integer(),
            sa.ForeignKey('secrets_pki_secret_representations.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('secret_version', sa.Integer(), nullable=False),
        sa.Column('source_revision', sa.String(40), nullable=False),
        sa.Column('profile_key', sa.String(80), nullable=False),
        sa.Column('operation_key', sa.String(120), nullable=False),
        sa.CheckConstraint('secret_version > 0', name='ck_access_auto_credential_version'),
        sa.CheckConstraint('length(host_revision) = 64', name='ck_access_auto_credential_host_revision'),
        sa.CheckConstraint('length(reference_fingerprint) = 64', name='ck_access_auto_credential_reference'),
        sa.CheckConstraint('length(source_revision) = 40', name='ck_access_auto_credential_source'),
        sa.CheckConstraint(
            "profile_key <> '' AND profile_key NOT LIKE '%*%' AND operation_key <> '' AND operation_key NOT LIKE '%*%'",
            name='ck_access_auto_credential_operation',
        ),
    )


def downgrade() -> None:
    # Refuse lossy downgrade: retain exact policy evidence and revisions.
    connection = op.get_bind()
    count = connection.execute(
        sa.text("SELECT COUNT(*) FROM access_scope_policies WHERE scope_level = 'automation_credential'")
    ).scalar_one()
    targets = connection.execute(sa.text('SELECT COUNT(*) FROM access_automation_credential_targets')).scalar_one()
    if count or targets:
        raise RuntimeError('Exact automation credential scope evidence must be retained before downgrade.')
    op.drop_table('access_automation_credential_targets')
    with op.batch_alter_table('access_scope_policies') as batch:
        batch.drop_constraint('ck_access_scope_policy_credential_permission', type_='check')
        batch.drop_constraint('ck_access_scope_policy_exact_target', type_='check')
        batch.drop_constraint('ck_access_scope_policy_level', type_='check')
        batch.create_check_constraint('ck_access_scope_policy_level', "scope_level IN ('instance', 'vault_mount')")
        batch.create_check_constraint(
            'ck_access_scope_policy_exact_target',
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            " OR (scope_level = 'vault_mount' AND provider_namespace IS NOT NULL"
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
        )
