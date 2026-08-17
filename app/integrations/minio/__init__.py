from datetime import UTC, datetime

from app.integrations.minio.adapter import runtime_adapter
from app.integrations.minio.capabilities import (
    CAPABILITY_KEYS,
    COMPATIBILITY_PROFILES,
)
from app.integrations.minio.presentation import build_runtime_overview_rows
from app.integrations.registry import (
    IntegrationImplementation,
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.models.minio import MinioInstance


def _detail_url(instance: MinioInstance, section: str) -> str:
    return f'/integrations/minio/instances/{instance.id}#{section}'


def _record_failure(instance: MinioInstance, error: Exception) -> None:
    now = datetime.now(UTC)
    instance.last_checked_at = now
    instance.last_status = 'disconnected'
    instance.last_error = str(error)[:1000]
    instance.last_response_time_ms = None
    instance.object_storage_system.status = 'failed'
    instance.object_storage_system.last_check = now


integration_module = IntegrationModule(
    integration_type='object_storage',
    label='Object Storage',
    domain_key='storage',
    capability_key='object_storage',
    icon='database',
    description='Provider-neutral object-storage registration, adapter validation, and asset-scoped observability binding.',
    workspace_endpoint='minio.index',
    module_path='app.integrations.minio',
    worker_queue='integration-runtime',
    worker_domain='storage-object',
    operation_queues={
        'connection.test': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
    },
    operations=frozenset(
        {
            'connection.test',
            'runtime.validate',
            'runtime.health',
            'runtime.state',
        }
    ),
    capability_keys=CAPABILITY_KEYS,
    compatibility_profiles=COMPATIBILITY_PROFILES,
    runtime_label='Object Storage',
    navigation_endpoint_prefixes=('minio.',),
)

provider_implementation = IntegrationImplementation(
    integration_type='object_storage',
    provider_key='minio',
    adapter_key='s3',
    adapter=runtime_adapter,
    instance_loader=model_loader(MinioInstance),
    canonical_record_loader=canonical_model_loader(MinioInstance),
    module_path='app.integrations.minio',
    detail_url_builder=_detail_url,
    failure_recorder=_record_failure,
    runtime_overview_builder=build_runtime_overview_rows,
)

registry.register(integration_module)
registry.register_implementation(provider_implementation)
