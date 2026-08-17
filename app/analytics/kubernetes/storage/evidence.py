from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles import get_kubernetes_query_expression
from app.metrics_sources.consumer import MetricsConsumer

STORAGE_QUERY_CAPABILITIES = (
    'instant_query',
    'kubernetes_identity',
)

NAMESPACE_ACTIVE_QUERY = get_kubernetes_query_expression('analytics.storage.queries.NAMESPACE_ACTIVE_QUERY')
NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY = get_kubernetes_query_expression(
    'analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY'
)
NODE_ROOT_FILESYSTEM_SIZE_QUERY = get_kubernetes_query_expression(
    'analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY'
)
NODE_VAR_FILESYSTEM_AVAILABLE_QUERY = get_kubernetes_query_expression(
    'analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY'
)
NODE_VAR_FILESYSTEM_SIZE_QUERY = get_kubernetes_query_expression(
    'analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY'
)
PVC_AVAILABLE_BY_CLAIM_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY')
PVC_CAPACITY_BY_CLAIM_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PVC_CAPACITY_BY_CLAIM_QUERY')
PVC_INFO_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PVC_INFO_QUERY')
PVC_REQUESTED_BY_CLAIM_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PVC_REQUESTED_BY_CLAIM_QUERY')
PVC_STATUS_BY_CLAIM_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PVC_STATUS_BY_CLAIM_QUERY')
PVC_USED_BY_CLAIM_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY')
PV_CAPACITY_BY_VOLUME_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PV_CAPACITY_BY_VOLUME_QUERY')
PV_INFO_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PV_INFO_QUERY')
PV_STATUS_BY_VOLUME_QUERY = get_kubernetes_query_expression('analytics.storage.queries.PV_STATUS_BY_VOLUME_QUERY')


@dataclass(frozen=True, slots=True)
class VectorEvidence:
    rows: tuple[dict[str, Any], ...] = ()
    observed: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class StorageEvidence:
    namespaces: VectorEvidence
    filesystem_var_size: VectorEvidence
    filesystem_var_available: VectorEvidence
    filesystem_root_size: VectorEvidence
    filesystem_root_available: VectorEvidence
    pvc_requested: VectorEvidence
    pvc_capacity: VectorEvidence
    pvc_used: VectorEvidence
    pvc_available: VectorEvidence
    pvc_status: VectorEvidence
    pvc_info: VectorEvidence
    pv_capacity: VectorEvidence
    pv_status: VectorEvidence
    pv_info: VectorEvidence


class StorageEvidenceCollector:
    """Collect every Storage Analytics query once for one materialization run."""

    def __init__(self, consumer: MetricsConsumer) -> None:
        self.consumer = consumer

    def query(self, expression: str) -> VectorEvidence:
        try:
            response = self.consumer.query(
                expression,
                required_capabilities=STORAGE_QUERY_CAPABILITIES,
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
        return VectorEvidence(rows=rows, observed=True)

    def collect(self) -> StorageEvidence:
        return StorageEvidence(
            namespaces=self.query(NAMESPACE_ACTIVE_QUERY),
            filesystem_var_size=self.query(NODE_VAR_FILESYSTEM_SIZE_QUERY),
            filesystem_var_available=self.query(NODE_VAR_FILESYSTEM_AVAILABLE_QUERY),
            filesystem_root_size=self.query(NODE_ROOT_FILESYSTEM_SIZE_QUERY),
            filesystem_root_available=self.query(NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY),
            pvc_requested=self.query(PVC_REQUESTED_BY_CLAIM_QUERY),
            pvc_capacity=self.query(PVC_CAPACITY_BY_CLAIM_QUERY),
            pvc_used=self.query(PVC_USED_BY_CLAIM_QUERY),
            pvc_available=self.query(PVC_AVAILABLE_BY_CLAIM_QUERY),
            pvc_status=self.query(PVC_STATUS_BY_CLAIM_QUERY),
            pvc_info=self.query(PVC_INFO_QUERY),
            pv_capacity=self.query(PV_CAPACITY_BY_VOLUME_QUERY),
            pv_status=self.query(PV_STATUS_BY_VOLUME_QUERY),
            pv_info=self.query(PV_INFO_QUERY),
        )


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
