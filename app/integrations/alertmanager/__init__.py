from app.integrations.alertmanager.adapter import runtime_adapter
from app.integrations.alertmanager.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import (
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.models.alertmanager import AlertmanagerInstance


def _detail_url(instance: AlertmanagerInstance, section: str) -> str:
    return f'/integrations/alertmanager/instances/{instance.id}#{section}'


integration_module = IntegrationModule(
    provider_type='alertmanager',
    label='Alertmanager',
    domain_key='observability',
    capability_key='alerting',
    icon='siren',
    description=(
        'Shared alerting providers, asset bindings, alert retrieval, silence capability, '
        'and API compatibility validation.'
    ),
    workspace_endpoint='integrations.alertmanager',
    adapter=runtime_adapter,
    instance_loader=model_loader(AlertmanagerInstance),
    canonical_record_loader=canonical_model_loader(AlertmanagerInstance),
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
    detail_url_builder=_detail_url,
)

registry.register(integration_module)
