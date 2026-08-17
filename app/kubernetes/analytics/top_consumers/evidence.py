from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.integrations.observability.metrics_source.application.consumer import MetricsConsumer
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles import get_kubernetes_query_expression

TOP_CONSUMERS_QUERY_CAPABILITIES = ('instant_query',)
TOP_CONSUMERS_ADVISORY_CAPABILITIES = (
    'kubernetes_identity',
    'workload_metrics',
    'resource_requests_limits',
    'capacity_metrics',
    'pvc_usage',
)

NAMESPACE_ACTIVE_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.NAMESPACE_ACTIVE_QUERY')
TOP_CPU_CONSUMERS_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY')
TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY'
)
CPU_REQUEST_BY_CONTAINER_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_QUERY'
)
CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY'
)
CPU_LIMIT_BY_CONTAINER_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_QUERY'
)
CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY'
)
CPU_ALLOCATABLE_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.CPU_ALLOCATABLE_QUERY')
TOTAL_CPU_USAGE_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOTAL_CPU_USAGE_QUERY')
TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY'
)
TOP_MEMORY_CONSUMERS_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY'
)
TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY'
)
MEMORY_REQUEST_BY_CONTAINER_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_QUERY'
)
MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY'
)
MEMORY_LIMIT_BY_CONTAINER_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_QUERY'
)
MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY'
)
MEMORY_ALLOCATABLE_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.MEMORY_ALLOCATABLE_QUERY')
TOTAL_MEMORY_USAGE_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_QUERY')
TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY'
)
POD_OWNER_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.POD_OWNER_QUERY')
POD_OWNER_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.POD_OWNER_BY_NAMESPACE_QUERY'
)
TOP_POD_CONSUMERS_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOP_POD_CONSUMERS_QUERY')
TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY'
)
POD_CAPACITY_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.POD_CAPACITY_QUERY')
TOTAL_RUNNING_PODS_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOTAL_RUNNING_PODS_QUERY')
TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY'
)
TOP_PVC_CONSUMERS_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOP_PVC_CONSUMERS_QUERY')
TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY'
)
PVC_CAPACITY_BY_CLAIM_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_QUERY'
)
PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY'
)
TOTAL_PVC_USED_QUERY = get_kubernetes_query_expression('analytics.top_consumers.queries.TOTAL_PVC_USED_QUERY')
TOTAL_PVC_USED_BY_NAMESPACE_QUERY = get_kubernetes_query_expression(
    'analytics.top_consumers.queries.TOTAL_PVC_USED_BY_NAMESPACE_QUERY'
)


@dataclass(frozen=True, slots=True)
class VectorEvidence:
    rows: tuple[dict[str, Any], ...] = ()
    observed: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ScalarEvidence:
    value: float = 0.0
    available: bool = False
    observed: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TopConsumersEvidence:
    namespaces: VectorEvidence
    pod_owners: VectorEvidence
    cpu_usage: VectorEvidence
    cpu_requests: VectorEvidence
    cpu_limits: VectorEvidence
    cpu_total: ScalarEvidence
    cpu_capacity: ScalarEvidence
    memory_usage: VectorEvidence
    memory_requests: VectorEvidence
    memory_limits: VectorEvidence
    memory_total: ScalarEvidence
    memory_capacity: ScalarEvidence
    pod_usage: VectorEvidence
    pod_total: ScalarEvidence
    pod_capacity: ScalarEvidence
    pvc_usage: VectorEvidence
    pvc_capacity: VectorEvidence
    pvc_total: ScalarEvidence


class TopConsumersEvidenceCollector:
    """Collect each Top Consumers signal once for one snapshot variant."""

    def __init__(self, consumer: MetricsConsumer) -> None:
        self.consumer = consumer

    def query(
        self,
        expression: str,
        *,
        advisory_capability: str = '',
        advisory_missing: frozenset[str] = frozenset(),
    ) -> VectorEvidence:
        try:
            response = self.consumer.query(
                expression,
                required_capabilities=TOP_CONSUMERS_QUERY_CAPABILITIES,
            )
        except MetricsSourceError as exc:
            return VectorEvidence(error=str(exc) or 'Metrics Source query failed.')

        if not isinstance(response, dict):
            return VectorEvidence(
                error=(f'Metrics Source returned {type(response).__name__}; expected a response mapping.')
            )
        data = response.get('data', {})
        result = data.get('result', []) if isinstance(data, dict) else []
        if not isinstance(result, list):
            return VectorEvidence(error='Metrics Source response data.result is not a list.')
        rows = tuple(item for item in result if isinstance(item, dict))
        if not rows and advisory_capability in advisory_missing:
            return VectorEvidence(
                error=(
                    f'{advisory_capability} capability evidence is unavailable; '
                    'an empty query result is not treated as confirmed zero.'
                )
            )
        return VectorEvidence(rows=rows, observed=True)

    def scalar(
        self,
        expression: str,
        *,
        advisory_capability: str = '',
        advisory_missing: frozenset[str] = frozenset(),
    ) -> ScalarEvidence:
        result = self.query(
            expression,
            advisory_capability=advisory_capability,
            advisory_missing=advisory_missing,
        )
        if not result.observed:
            return ScalarEvidence(error=result.error)
        first = next(
            (sample_value(item) for item in result.rows if sample_value(item) is not None),
            None,
        )
        if first is None:
            return ScalarEvidence(observed=True)
        return ScalarEvidence(value=first, available=True, observed=True)

    def collect(
        self,
        *,
        namespace: str,
        advisory_missing: frozenset[str] = frozenset(),
    ) -> TopConsumersEvidence:
        query = self.query
        scalar = self.scalar

        def namespaced(all_query: str, namespace_query_value: str) -> str:
            return namespace_query(namespace, all_query, namespace_query_value)

        return TopConsumersEvidence(
            namespaces=query(
                NAMESPACE_ACTIVE_QUERY,
                advisory_capability='kubernetes_identity',
                advisory_missing=advisory_missing,
            ),
            pod_owners=query(
                namespaced(POD_OWNER_QUERY, POD_OWNER_BY_NAMESPACE_QUERY),
                advisory_capability='kubernetes_identity',
                advisory_missing=advisory_missing,
            ),
            cpu_usage=query(
                namespaced(
                    TOP_CPU_CONSUMERS_QUERY,
                    TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='workload_metrics',
                advisory_missing=advisory_missing,
            ),
            cpu_requests=query(
                namespaced(
                    CPU_REQUEST_BY_CONTAINER_QUERY,
                    CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY,
                ),
                advisory_capability='resource_requests_limits',
                advisory_missing=advisory_missing,
            ),
            cpu_limits=query(
                namespaced(
                    CPU_LIMIT_BY_CONTAINER_QUERY,
                    CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY,
                ),
                advisory_capability='resource_requests_limits',
                advisory_missing=advisory_missing,
            ),
            cpu_total=scalar(
                namespaced(
                    TOTAL_CPU_USAGE_QUERY,
                    TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='workload_metrics',
                advisory_missing=advisory_missing,
            ),
            cpu_capacity=scalar(
                CPU_ALLOCATABLE_QUERY,
                advisory_capability='capacity_metrics',
                advisory_missing=advisory_missing,
            ),
            memory_usage=query(
                namespaced(
                    TOP_MEMORY_CONSUMERS_QUERY,
                    TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='workload_metrics',
                advisory_missing=advisory_missing,
            ),
            memory_requests=query(
                namespaced(
                    MEMORY_REQUEST_BY_CONTAINER_QUERY,
                    MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY,
                ),
                advisory_capability='resource_requests_limits',
                advisory_missing=advisory_missing,
            ),
            memory_limits=query(
                namespaced(
                    MEMORY_LIMIT_BY_CONTAINER_QUERY,
                    MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY,
                ),
                advisory_capability='resource_requests_limits',
                advisory_missing=advisory_missing,
            ),
            memory_total=scalar(
                namespaced(
                    TOTAL_MEMORY_USAGE_QUERY,
                    TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='workload_metrics',
                advisory_missing=advisory_missing,
            ),
            memory_capacity=scalar(
                MEMORY_ALLOCATABLE_QUERY,
                advisory_capability='capacity_metrics',
                advisory_missing=advisory_missing,
            ),
            pod_usage=query(
                namespaced(
                    TOP_POD_CONSUMERS_QUERY,
                    TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='kubernetes_identity',
                advisory_missing=advisory_missing,
            ),
            pod_total=scalar(
                namespaced(
                    TOTAL_RUNNING_PODS_QUERY,
                    TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='kubernetes_identity',
                advisory_missing=advisory_missing,
            ),
            pod_capacity=scalar(
                POD_CAPACITY_QUERY,
                advisory_capability='capacity_metrics',
                advisory_missing=advisory_missing,
            ),
            pvc_usage=query(
                namespaced(
                    TOP_PVC_CONSUMERS_QUERY,
                    TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='pvc_usage',
                advisory_missing=advisory_missing,
            ),
            pvc_capacity=query(
                namespaced(
                    PVC_CAPACITY_BY_CLAIM_QUERY,
                    PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY,
                ),
                advisory_capability='pvc_usage',
                advisory_missing=advisory_missing,
            ),
            pvc_total=scalar(
                namespaced(
                    TOTAL_PVC_USED_QUERY,
                    TOTAL_PVC_USED_BY_NAMESPACE_QUERY,
                ),
                advisory_capability='pvc_usage',
                advisory_missing=advisory_missing,
            ),
        )


def namespace_query(
    namespace: str,
    all_query: str,
    namespaced_query: str,
) -> str:
    if not namespace:
        return all_query
    escaped = namespace.replace('\\', '\\\\').replace('"', '\\"')
    return namespaced_query.replace('$namespace', escaped)


def sample_value(item: dict[str, Any]) -> float | None:
    value = item.get('value')
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    try:
        parsed = float(value[1])
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def sample_metric(item: dict[str, Any]) -> dict[str, Any]:
    metric = item.get('metric', {})
    return metric if isinstance(metric, dict) else {}


def metric_label(metric: dict[str, Any], label: str) -> str:
    value = metric.get(label, '')
    return value if isinstance(value, str) else ''
