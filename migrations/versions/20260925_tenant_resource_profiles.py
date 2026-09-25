"""add tenant resource profiles and namespace provisioning evidence

Revision ID: 20260925_tenant_profiles
Revises: 20260925_tenant_domain
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = '20260925_tenant_profiles'
down_revision = '20260925_tenant_domain'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_resource_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('profile_class', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quota_hard_json', sa.JSON(), nullable=False),
        sa.Column('limit_defaults_json', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "profile_class IN ('small', 'standard', 'large', 'custom')",
            name='ck_tenant_resource_profiles_class',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_tenant_resource_profiles_name'),
        sa.UniqueConstraint('public_id', name='uq_tenant_resource_profiles_public_id'),
    )
    op.create_index(
        'ix_tenant_resource_profiles_class_enabled',
        'tenant_resource_profiles',
        ['profile_class', 'enabled'],
    )

    op.add_column('tenant_namespaces', sa.Column('resource_profile_id', sa.Integer(), nullable=True))
    op.add_column(
        'tenant_namespaces',
        sa.Column('provisioning_status', sa.String(length=30), nullable=False, server_default='pending'),
    )
    op.add_column('tenant_namespaces', sa.Column('provisioning_message', sa.Text(), nullable=True))
    op.add_column('tenant_namespaces', sa.Column('desired_hash', sa.String(length=64), nullable=True))
    op.add_column('tenant_namespaces', sa.Column('effective_hash', sa.String(length=64), nullable=True))
    op.add_column('tenant_namespaces', sa.Column('provisioning_evidence_json', sa.JSON(), nullable=True))
    op.add_column('tenant_namespaces', sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_tenant_namespaces_resource_profile_id',
        'tenant_namespaces',
        'tenant_resource_profiles',
        ['resource_profile_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_check_constraint(
        'ck_tenant_namespaces_provisioning_status',
        'tenant_namespaces',
        "provisioning_status IN ('pending', 'ready', 'drifted', 'failed')",
    )
    op.create_index(
        'ix_tenant_namespaces_provisioning',
        'tenant_namespaces',
        ['cluster_id', 'provisioning_status'],
    )
    op.alter_column('tenant_namespaces', 'provisioning_status', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_tenant_namespaces_provisioning', table_name='tenant_namespaces')
    op.drop_constraint('ck_tenant_namespaces_provisioning_status', 'tenant_namespaces', type_='check')
    op.drop_constraint('fk_tenant_namespaces_resource_profile_id', 'tenant_namespaces', type_='foreignkey')
    op.drop_column('tenant_namespaces', 'last_reconciled_at')
    op.drop_column('tenant_namespaces', 'provisioning_evidence_json')
    op.drop_column('tenant_namespaces', 'effective_hash')
    op.drop_column('tenant_namespaces', 'desired_hash')
    op.drop_column('tenant_namespaces', 'provisioning_message')
    op.drop_column('tenant_namespaces', 'provisioning_status')
    op.drop_column('tenant_namespaces', 'resource_profile_id')
    op.drop_table('tenant_resource_profiles')
