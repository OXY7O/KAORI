from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.prometheus.consumer import PrometheusConsumer

CAPACITY_REQUIRED_CAPABILITIES = (
    'instant_query',
    'range_query',
    'kubernetes_identity',
    'capacity_metrics',
    'resource_requests_limits',
)

CURRENT_WORKER_PODS_QUERY = get_query_expression(
    'analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY'
)
READY_WORKER_NODE_COUNT_QUERY = get_query_expression(
    'analytics.capacity.queries.READY_WORKER_NODE_COUNT_QUERY'
)
WORKER_NODE_COUNT_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_NODE_COUNT_QUERY'
)
WORKER_CPU_ALLOCATABLE_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_CPU_ALLOCATABLE_QUERY'
)
WORKER_CPU_LIMITS_TOTAL_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_CPU_LIMITS_TOTAL_QUERY'
)
WORKER_CPU_PEAK_QUERY_TEMPLATE = get_query_expression(
    'analytics.capacity.queries.WORKER_CPU_PEAK_QUERY_TEMPLATE'
)
WORKER_CPU_REQUESTS_TOTAL_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_CPU_REQUESTS_TOTAL_QUERY'
)
WORKER_CPU_USAGE_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_CPU_USAGE_QUERY'
)
WORKER_MEMORY_ALLOCATABLE_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_ALLOCATABLE_QUERY'
)
WORKER_MEMORY_LIMITS_TOTAL_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_LIMITS_TOTAL_QUERY'
)
WORKER_MEMORY_PEAK_QUERY_TEMPLATE = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_PEAK_QUERY_TEMPLATE'
)
WORKER_MEMORY_REQUESTS_TOTAL_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_REQUESTS_TOTAL_QUERY'
)
WORKER_MEMORY_USAGE_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_USAGE_QUERY'
)
WORKER_POD_ALLOCATABLE_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_POD_ALLOCATABLE_QUERY'
)
NODE_FILESYSTEM_CAPACITY_QUERY = get_query_expression(
    'analytics.utilization.queries.STORAGE_CAPACITY'
)
NODE_FILESYSTEM_AVAILABLE_QUERY = get_query_expression(
    'analytics.utilization.queries.STORAGE_AVAILABLE'
)
NODE_FILESYSTEM_USAGE_QUERY = get_query_expression(
    'analytics.utilization.queries.STORAGE_USAGE'
)

CAPACITY_TIME_RANGE_STEP_MAP = {
    '1h': '5m',
    '6h': '15m',
    '12h': '30m',
    '24h': '1h',
    '7d': '6h',
    '30d': '12h',
    '60d': '1d',
}


def capacity_time_step(time_range: str) -> str:
    return CAPACITY_TIME_RANGE_STEP_MAP.get(time_range, '1h')


def build_range_query(query_template: str, time_range: str) -> str:
    return query_template.replace('__TIME_RANGE__', time_range).replace(
        '__TIME_STEP__', capacity_time_step(time_range)
    )


@dataclass(frozen=True, slots=True)
class ScalarEvidence:
    value: float = 0.0
    available: bool = False

    @property
    def positive(self) -> bool:
        return self.available and self.value > 0


@dataclass(frozen=True, slots=True)
class AllocationEvidence:
    allocatable: ScalarEvidence
    requests: ScalarEvidence
    limits: ScalarEvidence
    actual: ScalarEvidence
    peak: ScalarEvidence


@dataclass(frozen=True, slots=True)
class CapacityEvidence:
    worker_nodes: ScalarEvidence
    ready_worker_nodes: ScalarEvidence
    cpu: AllocationEvidence
    memory: AllocationEvidence
    pod_capacity: ScalarEvidence
    current_pods: ScalarEvidence
    filesystem_capacity: ScalarEvidence
    filesystem_used: ScalarEvidence
    filesystem_available: ScalarEvidence


class CapacityEvidenceCollector:
    """Collect every worker-capacity signal once for one materialization run."""

    def __init__(self, consumer: PrometheusConsumer) -> None:
        self.consumer = consumer

    def scalar(self, query: str) -> ScalarEvidence:
        response = self.consumer.query(
            query,
            required_capabilities=CAPACITY_REQUIRED_CAPABILITIES,
        )
        if not isinstance(response, dict):
            raise PrometheusError(
                f'Prometheus returned {type(response).__name__}; expected a response mapping.'
            )
        data = response.get('data', {})
        result = data.get('result', []) if isinstance(data, dict) else []
        if not isinstance(result, list):
            raise PrometheusError('Prometheus response data.result is not a list.')
        first = next((item for item in result if isinstance(item, dict)), None)
        if first is None:
            return ScalarEvidence()
        value = _extract_scalar(first)
        return ScalarEvidence(value=value, available=True) if value is not None else ScalarEvidence()

    def optional_scalar(self, query: str) -> ScalarEvidence:
        """Read an optional reference signal without blocking Capacity readiness."""
        try:
            response = self.consumer.query(
                query,
                required_capabilities=('instant_query',),
            )
        except PrometheusError:
            return ScalarEvidence()
        if not isinstance(response, dict):
            return ScalarEvidence()
        data = response.get('data', {})
        result = data.get('result', []) if isinstance(data, dict) else []
        if not isinstance(result, list):
            return ScalarEvidence()
        first = next((item for item in result if isinstance(item, dict)), None)
        if first is None:
            return ScalarEvidence()
        value = _extract_scalar(first)
        return ScalarEvidence(value=value, available=True) if value is not None else ScalarEvidence()

    def collect(self, *, time_range: str) -> CapacityEvidence:
        return CapacityEvidence(
            worker_nodes=self.scalar(WORKER_NODE_COUNT_QUERY),
            ready_worker_nodes=self.scalar(READY_WORKER_NODE_COUNT_QUERY),
            cpu=AllocationEvidence(
                allocatable=self.scalar(WORKER_CPU_ALLOCATABLE_QUERY),
                requests=self.scalar(WORKER_CPU_REQUESTS_TOTAL_QUERY),
                limits=self.scalar(WORKER_CPU_LIMITS_TOTAL_QUERY),
                actual=self.scalar(WORKER_CPU_USAGE_QUERY),
                peak=self.scalar(
                    build_range_query(WORKER_CPU_PEAK_QUERY_TEMPLATE, time_range)
                ),
            ),
            memory=AllocationEvidence(
                allocatable=self.scalar(WORKER_MEMORY_ALLOCATABLE_QUERY),
                requests=self.scalar(WORKER_MEMORY_REQUESTS_TOTAL_QUERY),
                limits=self.scalar(WORKER_MEMORY_LIMITS_TOTAL_QUERY),
                actual=self.scalar(WORKER_MEMORY_USAGE_QUERY),
                peak=self.scalar(
                    build_range_query(WORKER_MEMORY_PEAK_QUERY_TEMPLATE, time_range)
                ),
            ),
            pod_capacity=self.scalar(WORKER_POD_ALLOCATABLE_QUERY),
            current_pods=self.scalar(CURRENT_WORKER_PODS_QUERY),
            filesystem_capacity=self.optional_scalar(NODE_FILESYSTEM_CAPACITY_QUERY),
            filesystem_used=self.optional_scalar(NODE_FILESYSTEM_USAGE_QUERY),
            filesystem_available=self.optional_scalar(NODE_FILESYSTEM_AVAILABLE_QUERY),
        )


def _extract_scalar(item: dict[str, Any]) -> float | None:
    value = item.get('value')
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    try:
        parsed = float(value[1])
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None
