"""canonical Alertmanager bindings and Kubernetes connection authority

Revision ID: 20260719_cutover_p2
Revises: 20260718_runtime_v2
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

revision = '20260719_cutover_p2'
down_revision = '20260718_runtime_v2'
branch_labels = None
depends_on = None


_ALERTMANAGER_CAPABILITIES = (
    '["alerts", "alerts_v2", "silences", "silences_v2", '
    '"routing", "receivers", "status_v2"]'
)


def upgrade() -> None:
    # New cluster writes persist credentials only in kubernetes_connections.
    # The legacy column remains temporarily for the later destructive cleanup.
    op.alter_column(
        'clusters',
        'kubeconfig',
        existing_type=sa.Text(),
        nullable=True,
    )

    # Normalize existing canonical Alertmanager bindings so both product-level
    # and API-contract capability keys can be resolved consistently.
    op.execute(
        sa.text(
            """
            UPDATE integration_bindings AS binding
            SET capability_scope = CAST(:capabilities AS json)
            FROM integration_instances AS instance
            WHERE instance.id = binding.integration_instance_id
              AND instance.provider_type = 'alertmanager'
            """
        ).bindparams(capabilities=_ALERTMANAGER_CAPABILITIES)
    )


def downgrade() -> None:
    # Restore legacy values before making the old column mandatory again.
    op.execute(
        """
        UPDATE clusters AS cluster
        SET kubeconfig = connection.kubeconfig
        FROM kubernetes_connections AS connection
        WHERE connection.cluster_id = cluster.id
          AND cluster.kubeconfig IS NULL
        """
    )
    op.alter_column(
        'clusters',
        'kubeconfig',
        existing_type=sa.Text(),
        nullable=False,
    )
