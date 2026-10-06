from datetime import UTC, datetime

from app.artifact_registry.collectors import register_registry_collector
from app.artifact_registry.governance import register_registry_governance_collector
from app.artifact_registry.security.providers import register_registry_security_collector
from app.common.integration_errors import describe_integration_failure
from app.integrations.kernel.registry import (
    canonical_model_loader,
    IntegrationImplementation,
    IntegrationModule,
    model_loader,
    registry,
)
from app.integrations.registry.providers.harbor.adapter import runtime_adapter
from app.integrations.registry.providers.harbor.capabilities import (
    COMPATIBILITY_PROFILES,
    CORE_CAPABILITY_KEYS,
)
from app.integrations.registry.providers.harbor.governance import collector as governance_collector
from app.integrations.registry.providers.harbor.inventory import collector as inventory_collector
from app.integrations.registry.providers.harbor.security import collector as security_collector
from app.models.harbor import HarborInstance
def _detail_url(instance: HarborInstance, section: str) -> str:
    suffix = f'#{section}' if section else ''
    return f'/integrations/registry/harbor/instances/{instance.id}{suffix}'


def _record_failure(instance: HarborInstance, error: Exception) -> None:
    now = datetime.now(UTC)
    failure = describe_integration_failure(
        error,
        service_name='Harbor',
        endpoint=instance.endpoint,
        request_path='/api/v2.0/health',
        timeout_seconds=min(max(int(instance.timeout or 5), 1), 30),
    )
    instance.last_checked_at = now
    instance.last_status = 'disconnected'
    instance.last_error = str(failure['detail'])[:1000]
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
register_registry_collector(inventory_collector)
register_registry_security_collector(security_collector)
register_registry_governance_collector(governance_collector)
