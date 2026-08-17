from app.integrations.kubernetes.adapter import runtime_adapter
from app.integrations.kubernetes.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import (
    IntegrationImplementation,
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.models.kubernetes import KubernetesConnection


def _detail_url(instance: KubernetesConnection, section: str) -> str:
    return f'/integrations/kubernetes/{instance.cluster_id}#{section}'


integration_module = IntegrationModule(
    integration_type='container_orchestrator',
    label='Container Orchestrators',
    domain_key='orchestration',
    capability_key='container_orchestrator',
    icon='boxes',
    description=('Container-orchestrator integrations backed by provider-specific access and stable runtime adapters.'),
    workspace_endpoint='integrations.kubernetes',
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
    navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.'),
)

provider_implementation = IntegrationImplementation(
    integration_type='container_orchestrator',
    provider_key='kubernetes',
    adapter_key='kubernetes_api',
    adapter=runtime_adapter,
    instance_loader=model_loader(KubernetesConnection),
    canonical_record_loader=canonical_model_loader(KubernetesConnection),
    module_path='app.integrations.kubernetes',
    detail_url_builder=_detail_url,
)

registry.register(integration_module)
registry.register_implementation(provider_implementation)
