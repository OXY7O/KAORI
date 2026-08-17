from datetime import UTC, datetime

from app.integrations.metrics.adapter import runtime_adapter
from app.integrations.metrics.capabilities import CAPABILITY_KEYS, COMPATIBILITY_PROFILES
from app.integrations.registry import IntegrationModule, canonical_model_loader, model_loader, registry
from app.models.metrics_source import MetricsSource


def _detail_url(instance: MetricsSource, section: str) -> str:
    return f'/integrations/metrics-sources/instances/{instance.id}#{section}'


def _record_failure(instance: MetricsSource, error: Exception) -> None:
    instance.last_checked_at = datetime.now(UTC)
    instance.last_status = 'disconnected'
    instance.last_error = str(error)[:1000]
    instance.last_response_time_ms = None


integration_module = IntegrationModule(
    provider_type='metrics_source',
    label='Metrics Sources',
    domain_key='observability',
    capability_key='metrics',
    icon='activity',
    description=(
        'Provider-neutral metrics source registration, query validation, consumer binding, '
        'and horizon-aware routing.'
    ),
    workspace_endpoint='integrations.metrics_sources',
    adapter=runtime_adapter,
    instance_loader=model_loader(MetricsSource),
    canonical_record_loader=canonical_model_loader(MetricsSource),
    module_path='app.integrations.metrics',
    worker_queue='integration-runtime',
    worker_domain='observability-metrics',
    operation_queues={
        'validation.session.build': 'inline',
        'query.session.build': 'inline',
        'query.instant': 'inline',
        'query.at': 'inline',
        'query.range': 'inline',
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
            'validation.session.build',
            'query.session.build',
            'query.instant',
            'query.at',
            'query.range',
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
    runtime_label='Metrics Sources',
    navigation_endpoint_prefixes=('integrations.metrics_sources', 'metrics.'),
    detail_url_builder=_detail_url,
    failure_recorder=_record_failure,
)

registry.register(integration_module)
