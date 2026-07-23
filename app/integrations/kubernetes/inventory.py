from __future__ import annotations

from app.models.kubernetes import KubernetesConnection


def synchronize_inventory(connection: KubernetesConnection):
    """Run the Kubernetes inventory domain use case through a canonical connection."""
    from app.inventory.synchronization import sync_inventory

    return sync_inventory(connection.cluster, connection)
