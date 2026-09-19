from app.integrations.observability.alert_source.providers.alertmanager.adapter import runtime_adapter
from app.integrations.observability.alert_source.providers.alertmanager.capabilities import (
    COMPATIBILITY_PROFILES,
    CORE_CAPABILITY_KEYS,
)
from app.integrations.registry import (
    IntegrationImplementation,
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.models.alertmanager import AlertmanagerInstance


def _detail_url(instance: AlertmanagerInstance, section: str) -> str:
    return f'/integrations/alertmanager/instances/{instance.id}#{section}'


integration_module = IntegrationModule(
    integration_type='alert_source',
    label='Alert Sources',
    domain_key='observability',
    capability_key='alert_source',
    icon='siren',
    description=(
        'Provider-neutral alert sources, asset bindings, alert retrieval, control capability, '
        'and adapter-specific runtime validation.'
    ),
    workspace_endpoint='integrations.alertmanager',
    module_path='app.integrations.observability.alert_source.providers.alertmanager',
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
    capability_keys=CORE_CAPABILITY_KEYS,
    compatibility_profiles=COMPATIBILITY_PROFILES,
    runtime_label='Alert Sources',
    navigation_endpoint_prefixes=('integrations.alertmanager', 'alertmanager.'),
)

provider_implementation = IntegrationImplementation(
    integration_type='alert_source',
    provider_key='alertmanager',
    adapter_key='alertmanager_api_v2',
    adapter=runtime_adapter,
    instance_loader=model_loader(AlertmanagerInstance),
    canonical_record_loader=canonical_model_loader(AlertmanagerInstance),
    module_path='app.integrations.observability.alert_source.providers.alertmanager',
    detail_url_builder=_detail_url,
)

registry.register(integration_module)
registry.register_implementation(provider_implementation)
