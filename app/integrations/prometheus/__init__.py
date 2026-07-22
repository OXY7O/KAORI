from app.integrations.prometheus.adapter import PrometheusRuntimeAdapter, runtime_adapter
from app.integrations.prometheus.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import IntegrationModule, model_loader, registry
from app.models.prometheus import PrometheusInstance

integration_module = IntegrationModule(
    provider_type='prometheus',
    label='Prometheus',
    adapter=runtime_adapter,
    instance_loader=model_loader(PrometheusInstance),
    module_path='app.integrations.prometheus',
    worker_queue='integration-runtime',
    worker_domain='observability-metrics',
    operation_queues={
        'client.build': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
        'binding.validate': 'integration-validation',
    },
    operations=frozenset({
        'client.build',
        'runtime.validate',
        'runtime.health',
        'runtime.state',
        'binding.validate',
    }),
    capability_keys=CAPABILITY_KEYS,
    compatibility_profiles=COMPATIBILITY_PROFILES,
)

registry.register(integration_module)

__all__ = ['PrometheusRuntimeAdapter', 'integration_module', 'runtime_adapter']
