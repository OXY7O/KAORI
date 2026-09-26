"""extend Tenant credential governance for CI/CD deployer identities

Revision ID: 20260926_tenant_deployer_credentials
Revises: 20260926_tenant_credentials
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = '20260926_tenant_deployer_credentials'
down_revision = '20260926_tenant_credentials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_tenant_memberships_principal_reference', 'tenant_memberships', type_='check')
    op.drop_constraint('ck_tenant_memberships_principal_type', 'tenant_memberships', type_='check')
    op.create_check_constraint(
        'ck_tenant_memberships_principal_type',
        'tenant_memberships',
        "principal_type IN ('user', 'group', 'service_account')",
    )
    op.create_check_constraint(
        'ck_tenant_memberships_principal_reference',
        'tenant_memberships',
        "((principal_type = 'user' AND user_id IS NOT NULL AND group_id IS NULL) "
        "OR (principal_type = 'group' AND group_id IS NOT NULL AND user_id IS NULL) "
        "OR (principal_type = 'service_account' AND user_id IS NULL AND group_id IS NULL))",
    )
    op.create_unique_constraint(
        'uq_tenant_memberships_tenant_principal_subject',
        'tenant_memberships',
        ['tenant_id', 'principal_type', 'subject_name'],
    )

    op.add_column('tenant_credentials', sa.Column('application_name', sa.String(length=120), nullable=True))
    op.drop_constraint('ck_tenant_credentials_type_scope', 'tenant_credentials', type_='check')
    op.drop_constraint('ck_tenant_credentials_delivery_method', 'tenant_credentials', type_='check')
    op.drop_constraint('ck_tenant_credentials_type', 'tenant_credentials', type_='check')
    op.create_check_constraint(
        'ck_tenant_credentials_type',
        'tenant_credentials',
        "credential_type IN ('human_service_account', 'admin_kubeconfig', 'deployer_service_account')",
    )
    op.create_check_constraint(
        'ck_tenant_credentials_delivery_method',
        'tenant_credentials',
        "delivery_method IN ('jumpserver', 'exceptional_kubeconfig', 'admin_kubeconfig', 'cicd_kubeconfig')",
    )
    op.create_check_constraint(
        'ck_tenant_credentials_type_scope',
        'tenant_credentials',
        "((credential_type = 'human_service_account' AND access_grant_id IS NOT NULL "
        'AND anchor_namespace_id IS NULL AND application_name IS NULL '
        "AND delivery_method IN ('jumpserver', 'exceptional_kubeconfig')) "
        "OR (credential_type = 'admin_kubeconfig' AND access_grant_id IS NULL "
        'AND anchor_namespace_id IS NOT NULL AND application_name IS NULL '
        "AND delivery_method = 'admin_kubeconfig') "
        "OR (credential_type = 'deployer_service_account' AND access_grant_id IS NOT NULL "
        'AND anchor_namespace_id IS NULL AND application_name IS NOT NULL '
        "AND delivery_method = 'cicd_kubeconfig'))",
    )
    op.create_index(
        'ix_tenant_credentials_application',
        'tenant_credentials',
        ['tenant_id', 'application_name', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_tenant_credentials_application', table_name='tenant_credentials')
    op.drop_constraint('ck_tenant_credentials_type_scope', 'tenant_credentials', type_='check')
    op.drop_constraint('ck_tenant_credentials_delivery_method', 'tenant_credentials', type_='check')
    op.drop_constraint('ck_tenant_credentials_type', 'tenant_credentials', type_='check')
    op.create_check_constraint(
        'ck_tenant_credentials_type',
        'tenant_credentials',
        "credential_type IN ('human_service_account', 'admin_kubeconfig')",
    )
    op.create_check_constraint(
        'ck_tenant_credentials_delivery_method',
        'tenant_credentials',
        "delivery_method IN ('jumpserver', 'exceptional_kubeconfig', 'admin_kubeconfig')",
    )
    op.create_check_constraint(
        'ck_tenant_credentials_type_scope',
        'tenant_credentials',
        "((credential_type = 'human_service_account' AND access_grant_id IS NOT NULL "
        'AND anchor_namespace_id IS NULL '
        "AND delivery_method IN ('jumpserver', 'exceptional_kubeconfig')) "
        "OR (credential_type = 'admin_kubeconfig' AND access_grant_id IS NULL "
        "AND anchor_namespace_id IS NOT NULL AND delivery_method = 'admin_kubeconfig'))",
    )
    op.drop_column('tenant_credentials', 'application_name')

    op.drop_constraint(
        'uq_tenant_memberships_tenant_principal_subject',
        'tenant_memberships',
        type_='unique',
    )
    op.drop_constraint('ck_tenant_memberships_principal_reference', 'tenant_memberships', type_='check')
    op.drop_constraint('ck_tenant_memberships_principal_type', 'tenant_memberships', type_='check')
    op.create_check_constraint(
        'ck_tenant_memberships_principal_type',
        'tenant_memberships',
        "principal_type IN ('user', 'group')",
    )
    op.create_check_constraint(
        'ck_tenant_memberships_principal_reference',
        'tenant_memberships',
        "((principal_type = 'user' AND user_id IS NOT NULL AND group_id IS NULL) "
        "OR (principal_type = 'group' AND group_id IS NOT NULL AND user_id IS NULL))",
    )
