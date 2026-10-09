"""Introduce provider-preserving Released Tenant and Namespace terminal states.

Revision ID: 20261009_tenant_released
Revises: 20261004_registry_analytics
Create Date: 2026-10-09
"""

from alembic import op

revision = '20261009_tenant_released'
down_revision = '20261004_registry_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_tenants_lifecycle_status', 'tenants', type_='check')
    op.create_check_constraint(
        'ck_tenants_lifecycle_status', 'tenants',
        "lifecycle_status IN ('pending', 'ready', 'degraded', 'decommissioning', 'decommissioned', 'released')",
    )
    op.drop_constraint('ck_tenant_namespaces_provisioning_status', 'tenant_namespaces', type_='check')
    op.create_check_constraint(
        'ck_tenant_namespaces_provisioning_status', 'tenant_namespaces',
        "provisioning_status IN ('pending', 'ready', 'drifted', 'failed', 'deprovisioning', 'deprovisioned', 'released')",
    )


def downgrade() -> None:
    # Never collapse provider-preserving Released into destructive Decommissioned.
    # Administrators must first reconcile/rollback released generations explicitly.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM tenants WHERE lifecycle_status = 'released') "
        "OR EXISTS (SELECT 1 FROM tenant_namespaces WHERE provisioning_status = 'released') "
        "THEN RAISE EXCEPTION 'Cannot downgrade with Released Tenant/Namespace history'; "
        "END IF; END $$;"
    )
    op.drop_constraint('ck_tenant_namespaces_provisioning_status', 'tenant_namespaces', type_='check')
    op.create_check_constraint(
        'ck_tenant_namespaces_provisioning_status', 'tenant_namespaces',
        "provisioning_status IN ('pending', 'ready', 'drifted', 'failed', 'deprovisioning', 'deprovisioned')",
    )
    op.drop_constraint('ck_tenants_lifecycle_status', 'tenants', type_='check')
    op.create_check_constraint(
        'ck_tenants_lifecycle_status', 'tenants',
        "lifecycle_status IN ('pending', 'ready', 'degraded', 'decommissioning', 'decommissioned')",
    )
