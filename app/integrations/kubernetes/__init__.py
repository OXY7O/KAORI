from app.integrations.kubernetes.adapter import KubernetesRuntimeAdapter, runtime_adapter
from app.integrations.kubernetes.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import IntegrationModule, model_loader, registry
from app.integrations.kubernetes.resolver import (
    KubernetesAssetRuntime,
    connection_for_cluster,
    kubeconfig_for_cluster,
    resolve_kubernetes_for_cluster,
    server_for_cluster,
    tls_policy_for_cluster,
)
from app.models.kubernetes import KubernetesConnection

integration_module = IntegrationModule(
    provider_type='kubernetes',
    label='Kubernetes',
    adapter=runtime_adapter,
    instance_loader=model_loader(KubernetesConnection),
    module_path='app.integrations.kubernetes',
    worker_queue='inventory',
    worker_domain='kubernetes',
    operation_queues={
        'client.build': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
        'inventory.sync': 'inventory',
    },
    operations=frozenset({'client.build', 'runtime.validate', 'runtime.health', 'runtime.state', 'inventory.sync'}),
    capability_keys=CAPABILITY_KEYS,
    compatibility_profiles=COMPATIBILITY_PROFILES,
)

registry.register(integration_module)

__all__ = [
    'KubernetesAssetRuntime',
    'KubernetesRuntimeAdapter',
    'connection_for_cluster',
    'integration_module',
    'kubeconfig_for_cluster',
    'resolve_kubernetes_for_cluster',
    'runtime_adapter',
    'server_for_cluster',
    'tls_policy_for_cluster',
]
