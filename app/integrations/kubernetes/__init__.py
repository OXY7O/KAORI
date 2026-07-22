from app.integrations.kubernetes.adapter import runtime_adapter
from app.integrations.kubernetes.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import IntegrationModule, model_loader, registry
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
