from datetime import UTC, datetime

from app.integrations.kernel.registry import (
    IntegrationImplementation,
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.integrations.registry.providers.harbor.adapter import runtime_adapter
from app.integrations.registry.providers.harbor.capabilities import (
    COMPATIBILITY_PROFILES,
    CORE_CAPABILITY_KEYS,
)
from app.models.harbor import HarborInstance


def _detail_url(instance: HarborInstance, section: str) -> str:
    suffix = f'#{section}' if section else ''
    return f'/integrations/registry/harbor/instances/{instance.id}{suffix}'


def _record_failure(instance: HarborInstance, error: Exception) -> None:
    now = datetime.now(UTC)
    instance.last_checked_at = now
    instance.last_status = 'disconnected'
    instance.last_error = str(error)[:1000]
    instance.last_response_time_ms = None


integration_module = IntegrationModule(
    integration_type='registry',
    label='Registry',
    domain_key='registry',
    capability_key='registry',
    icon='package',
    description='Provider-neutral OCI Registry connectivity, readiness, and committed evidence.',
    workspace_endpoint='harbor.index',
    module_path='app.integrations.registry.providers.harbor',
    worker_queue='integration-runtime',
    worker_domain='registry-provider',
    operation_queues={
        'connection.test': 'inline',
        'client.build': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
    },
    operations=frozenset(
        {
            'connection.test',
            'client.build',
            'runtime.validate',
            'runtime.health',
            'runtime.state',
        }
    ),
    capability_keys=CORE_CAPABILITY_KEYS,
    compatibility_profiles=COMPATIBILITY_PROFILES,
    runtime_label='Registry',
    navigation_endpoint_prefixes=('harbor.',),
)

provider_implementation = IntegrationImplementation(
    integration_type='registry',
    provider_key='harbor',
    adapter_key='harbor_api_v2',
    adapter=runtime_adapter,
    instance_loader=model_loader(HarborInstance),
    canonical_record_loader=canonical_model_loader(HarborInstance),
    module_path='app.integrations.registry.providers.harbor',
    detail_url_builder=_detail_url,
    failure_recorder=_record_failure,
)

registry.register(integration_module)
registry.register_implementation(provider_implementation)
