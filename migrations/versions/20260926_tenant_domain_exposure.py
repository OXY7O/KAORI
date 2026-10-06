"""add Tenant domain reservation and exposure policy

Revision ID: 20260926_tenant_domain_policy
Revises: 20260926_tenant_managed_res
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = '20260926_tenant_domain_policy'
down_revision = '20260926_tenant_managed_res'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_domain_reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_environment_id', sa.Integer(), nullable=False),
        sa.Column('hostname_pattern', sa.String(length=253), nullable=False),
        sa.Column('match_mode', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "match_mode IN ('exact', 'wildcard', 'regex')",
            name='ck_tenant_domain_reservations_match_mode',
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name='ck_tenant_domain_reservations_status',
        ),
        sa.ForeignKeyConstraint(['tenant_environment_id'], ['tenant_environments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_domain_reservations_public_id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_domain_reservations_correlation_id'),
        sa.UniqueConstraint(
            'tenant_environment_id',
            'hostname_pattern',
            'match_mode',
            name='uq_tenant_domain_reservations_environment_pattern',
        ),
    )
    op.create_index(
        'ix_tenant_domain_reservations_tenant_status',
        'tenant_domain_reservations',
        ['tenant_id', 'status'],
    )
    op.create_index(
        'ix_tenant_domain_reservations_environment',
        'tenant_domain_reservations',
        ['tenant_environment_id', 'status'],
    )

    op.create_table(
        'tenant_exposure_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_namespace_id', sa.Integer(), nullable=False),
        sa.Column('profile_key', sa.String(length=40), nullable=False),
        sa.Column('allow_cluster_ip', sa.Boolean(), nullable=False),
        sa.Column('allow_ingress', sa.Boolean(), nullable=False),
        sa.Column('allow_node_port', sa.Boolean(), nullable=False),
        sa.Column('allow_load_balancer', sa.Boolean(), nullable=False),
        sa.Column('allow_external_name', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name='ck_tenant_exposure_policies_status',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_namespace_id'], ['tenant_namespaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id', name='uq_tenant_exposure_policies_public_id'),
        sa.UniqueConstraint('correlation_id', name='uq_tenant_exposure_policies_correlation_id'),
        sa.UniqueConstraint('tenant_namespace_id', name='uq_tenant_exposure_policies_namespace'),
    )
    op.create_index(
        'ix_tenant_exposure_policies_tenant_status',
        'tenant_exposure_policies',
        ['tenant_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_tenant_exposure_policies_tenant_status', table_name='tenant_exposure_policies')
    op.drop_table('tenant_exposure_policies')
    op.drop_index('ix_tenant_domain_reservations_environment', table_name='tenant_domain_reservations')
    op.drop_index('ix_tenant_domain_reservations_tenant_status', table_name='tenant_domain_reservations')
    op.drop_table('tenant_domain_reservations')
