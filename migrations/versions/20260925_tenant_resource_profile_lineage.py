"""lock built-in Tenant Resource Profiles and add Custom lineage

Revision ID: 20260925_tenant_profile_lineage
Revises: 20260925_tenant_allocations
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = '20260925_tenant_profile_lineage'
down_revision = '20260925_tenant_allocations'
branch_labels = None
depends_on = None

_PRESETS = {
    'small': {
        'quota': {
            'requests.cpu': '1',
            'limits.cpu': '2',
            'requests.memory': '2Gi',
            'limits.memory': '4Gi',
            'pods': '10',
            'persistentvolumeclaims': '5',
            'requests.storage': '50Gi',
            'services': '5',
            'configmaps': '25',
            'secrets': '25',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '250m', 'memory': '256Mi'},
        },
    },
    'standard': {
        'quota': {
            'requests.cpu': '2',
            'limits.cpu': '4',
            'requests.memory': '4Gi',
            'limits.memory': '8Gi',
            'pods': '20',
            'persistentvolumeclaims': '10',
            'requests.storage': '100Gi',
            'services': '10',
            'configmaps': '50',
            'secrets': '50',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '500m', 'memory': '512Mi'},
        },
    },
    'large': {
        'quota': {
            'requests.cpu': '4',
            'limits.cpu': '8',
            'requests.memory': '8Gi',
            'limits.memory': '16Gi',
            'pods': '40',
            'persistentvolumeclaims': '20',
            'requests.storage': '200Gi',
            'services': '20',
            'configmaps': '100',
            'secrets': '100',
        },
        'limits': {
            'default_request': {'cpu': '250m', 'memory': '256Mi'},
            'default': {'cpu': '1', 'memory': '1Gi'},
        },
    },
}


def upgrade() -> None:
    op.add_column(
        'tenant_resource_profiles',
        sa.Column('base_preset_class', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'tenant_resource_profiles',
        sa.Column('base_preset_version', sa.Integer(), nullable=True),
    )

    profiles = sa.table(
        'tenant_resource_profiles',
        sa.column('profile_class', sa.String(length=20)),
        sa.column('version', sa.Integer()),
        sa.column('quota_hard_json', sa.JSON()),
        sa.column('limit_defaults_json', sa.JSON()),
    )
    for profile_class, preset in _PRESETS.items():
        op.execute(
            profiles.update()
            .where(profiles.c.profile_class == profile_class)
            .values(
                version=1,
                quota_hard_json=preset['quota'],
                limit_defaults_json=preset['limits'],
            )
        )


def downgrade() -> None:
    op.drop_column('tenant_resource_profiles', 'base_preset_version')
    op.drop_column('tenant_resource_profiles', 'base_preset_class')
