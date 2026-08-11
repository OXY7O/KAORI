from datetime import UTC, datetime

from app.integrations.prometheus.adapter import runtime_adapter
from app.integrations.prometheus.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import (
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.models.prometheus import PrometheusInstance


def _detail_url(instance: PrometheusInstance, section: str) -> str:
    return f'/integrations/prometheus/instances/{instance.id}#{section}'


def _record_failure(instance: PrometheusInstance, error: Exception) -> None:
    instance.last_checked_at = datetime.now(UTC)
    instance.last_status = 'disconnected'
    instance.last_error = str(error)[:1000]
    instance.last_response_time_ms = None


integration_module = IntegrationModule(
    provider_type='prometheus',
    label='Prometheus',
    domain_key='observability',
    capability_key='metrics',
    icon='activity',
    description='Metrics collection and versioned PromQL validation for connected infrastructure assets.',
    workspace_endpoint='integrations.prometheus',
    adapter=runtime_adapter,
    instance_loader=model_loader(PrometheusInstance),
    canonical_record_loader=canonical_model_loader(PrometheusInstance),
    module_path='app.integrations.prometheus',
    worker_queue='integration-runtime',
    worker_domain='observability-metrics',
    operation_queues={
        'client.build': 'inline',
        'connection.test': 'inline',
        'query_profile.audit': 'integration-validation',
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
            'connection.test',
            'query_profile.audit',
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
    runtime_label='Prometheus / Thanos',
    detail_url_builder=_detail_url,
    failure_recorder=_record_failure,
)

registry.register(integration_module)
