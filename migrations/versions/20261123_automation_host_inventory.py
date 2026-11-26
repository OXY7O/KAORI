"""Introduce canonical nonproduction host identities and Ansible inventory intent (#5161).

Revision ID: 20261123_automation_hosts
Revises: 20261112_internal_pki

No SSH private key, passwords, sudo secrets, provider token or kubeconfig
is persisted in these tables. Admission state is separate from identity.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261123_automation_hosts'
down_revision = '20261112_internal_pki'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'automation_host_assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(96), nullable=False),
        sa.Column('environment', sa.String(40), nullable=False),
        sa.Column('address', sa.String(45), nullable=False),
        sa.Column('ssh_port', sa.Integer(), nullable=False),
        sa.Column('lifecycle_status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('environment', 'address', name='uq_automation_host_env_ip'),
        sa.UniqueConstraint('environment', 'name', name='uq_automation_host_env_name'),
    )
    op.create_index('ix_automation_host_scope', 'automation_host_assets', ['environment', 'lifecycle_status'])
    op.create_table(
        'automation_inventory_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'host_id',
            sa.String(36),
            sa.ForeignKey('automation_host_assets.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('role', sa.String(40), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('integration_instance_id', 'host_id', name='uq_automation_assignment_instance_host'),
    )
    op.create_index(
        'ix_automation_assignment_instance', 'automation_inventory_assignments', ['integration_instance_id', 'enabled']
    )


def downgrade() -> None:
    op.drop_index('ix_automation_assignment_instance', table_name='automation_inventory_assignments')
    op.drop_table('automation_inventory_assignments')
    op.drop_index('ix_automation_host_scope', table_name='automation_host_assets')
    op.drop_table('automation_host_assets')
