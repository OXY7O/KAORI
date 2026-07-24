from app.integrations.alertmanager.adapter import runtime_adapter
from app.integrations.alertmanager.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import IntegrationModule, model_loader, registry
from app.models.alertmanager import AlertmanagerInstance

integration_module = IntegrationModule(
    provider_type='alertmanager',
    label='Alertmanager',
    adapter=runtime_adapter,
    instance_loader=model_loader(AlertmanagerInstance),
    module_path='app.integrations.alertmanager',
    worker_queue='integration-runtime',
    worker_domain='observability-alerts',
    operation_queues={
        'client.build': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
        'binding.create': 'inline',
        'binding.selector.update': 'inline',
        'binding.validate': 'integration-validation',
    },
    operations=frozenset(
        {
            'client.build',
            'runtime.validate',
            'runtime.health',
            'runtime.state',
            'binding.create',
            'binding.selector.update',
            'binding.validate',
        }
    ),
    capability_keys=CAPABILITY_KEYS,
    compatibility_profiles=COMPATIBILITY_PROFILES,
)

registry.register(integration_module)
