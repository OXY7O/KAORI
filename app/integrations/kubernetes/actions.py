from __future__ import annotations

from app.integrations.registry import execute_integration_operation
from app.models.kubernetes import KubernetesConnection


def execute_kubernetes_action(
    connection: KubernetesConnection,
    operation: str,
    **kwargs,
):
    return execute_integration_operation(
        'kubernetes',
        operation,
        instance=connection,
        **kwargs,
    )
