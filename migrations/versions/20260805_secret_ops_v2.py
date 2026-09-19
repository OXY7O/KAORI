"""retire legacy TLS mutation permissions

Revision ID: 20260805_secret_ops_v2
Revises: 20260805_config_inventory_v2
Create Date: 2026-08-05
"""

from alembic import op

revision = '20260805_secret_ops_v2'
down_revision = '20260805_config_inventory_v2'
branch_labels = None
depends_on = None

_PERMISSION_MAPPINGS = (
    ('tls_certificates.update', 'kubernetes_secrets.rotate_tls'),
    ('tls_certificates.bulk_update', 'kubernetes_secrets.bulk_rotate_tls'),
)


def _migrate_assignments(source_key: str, target_key: str) -> None:
    op.execute(
        f"""
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT source_assignment.role_id, target_permission.id, CURRENT_TIMESTAMP
        FROM role_permissions AS source_assignment
        JOIN permissions AS source_permission
          ON source_permission.id = source_assignment.permission_id
        JOIN permissions AS target_permission
          ON target_permission.key = '{target_key}'
        WHERE source_permission.key = '{source_key}'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def upgrade() -> None:
    for retired_key, canonical_key in _PERMISSION_MAPPINGS:
        _migrate_assignments(retired_key, canonical_key)

    retired = "', '".join(source for source, _ in _PERMISSION_MAPPINGS)
    op.execute(
        f"""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE key IN ('{retired}')
        )
        """
    )
    op.execute(f"DELETE FROM permissions WHERE key IN ('{retired}')")


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (key, module, action, description, created_at)
        VALUES
          (
            'tls_certificates.update',
            'governance',
            'update_tls_certificates',
            'Update an existing Kubernetes TLS Secret using a validated certificate and private key upload.',
            CURRENT_TIMESTAMP
          ),
          (
            'tls_certificates.bulk_update',
            'governance',
            'bulk_update_tls_certificates',
            'Update multiple selected Kubernetes TLS Secrets using a validated certificate and private key upload.',
            CURRENT_TIMESTAMP
          )
        ON CONFLICT (key) DO NOTHING
        """
    )
    for retired_key, canonical_key in _PERMISSION_MAPPINGS:
        _migrate_assignments(canonical_key, retired_key)
