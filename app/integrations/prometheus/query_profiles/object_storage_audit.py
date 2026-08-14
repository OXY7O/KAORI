from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.integrations.prometheus.exceptions import PrometheusError, PrometheusQueryError
from app.integrations.prometheus.query_profiles.object_storage_v1 import (
    PROFILE_KEY,
    PROFILE_LABEL,
    list_object_storage_queries,
)
from app.integrations.prometheus.query_profiles.types import QueryDefinition

_DOMAIN_LABELS = {
    'object_storage_capacity': 'Capacity & Usage',
    'object_storage_health': 'Health',
    'object_storage_performance': 'Performance',
    'object_storage_consumers': 'Bucket Consumers',
}

_QUERY_LABELS = {
    'object_storage.capacity.total_bytes': 'Usable Capacity',
    'object_storage.capacity.free_bytes': 'Free Capacity',
    'object_storage.usage.total_bytes': 'Used Capacity',
    'object_storage.usage.objects': 'Object Count',
    'object_storage.usage.buckets': 'Bucket Count',
    'object_storage.health.offline_nodes': 'Offline Nodes',
    'object_storage.requests.rate': 'Request Rate',
    'object_storage.requests.error_rate': 'Error Rate',
    'object_storage.requests.inflight': 'Inflight Requests',
    'object_storage.requests.waiting': 'Waiting Requests',
    'object_storage.traffic.received_bps': 'Traffic Received',
    'object_storage.traffic.sent_bps': 'Traffic Sent',
    'object_storage.bucket.usage': 'Bucket Usage',
    'object_storage.bucket.objects': 'Bucket Objects',
    'object_storage.bucket.quota': 'Bucket Quota',
    'object_storage.bucket.request_rate': 'Bucket Request Rate',
    'object_storage.bucket.error_rate': 'Bucket Error Rate',
}


class ObjectStoragePrometheusProfileAuditor:
    """Validate the MinIO v2 Object Storage query contract against one scoped Prometheus binding."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def audit(self, *, execute_queries: bool = True) -> dict[str, Any]:
        definitions = list_object_storage_queries()
        series = self._scoped_series(definitions)
        observed_metrics, metric_labels, metric_series_count = self._series_evidence(series)
        items = [
            self._audit_query(
                definition,
                observed_metrics=observed_metrics,
                metric_labels=metric_labels,
                metric_series_count=metric_series_count,
                execute_queries=execute_queries,
            )
            for definition in definitions
        ]

        summary = self._summary(items)
        return {
            'profile': PROFILE_KEY,
            'profile_label': PROFILE_LABEL,
            'checked_at': datetime.now(UTC).isoformat(),
            'status': summary['status'],
            'summary': summary,
            'domain_summary': self._domain_summary(items),
            'observed_metrics': sorted(observed_metrics),
            'items': items,
        }

    def _scoped_series(self, definitions: tuple[QueryDefinition, ...]) -> list[dict[str, Any]]:
        metrics = sorted({metric for definition in definitions for metric in definition.required_metrics})
        payload = self.client.series(metrics)
        if not isinstance(payload, dict) or payload.get('status') != 'success':
            raise PrometheusQueryError('Prometheus series discovery returned an unsuccessful response.')
        data = payload.get('data')
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    @staticmethod
    def _series_evidence(
        series: list[dict[str, Any]],
    ) -> tuple[set[str], dict[str, set[str]], dict[str, int]]:
        observed_metrics: set[str] = set()
        metric_labels: dict[str, set[str]] = defaultdict(set)
        metric_series_count: dict[str, int] = defaultdict(int)
        for row in series:
            metric = str(row.get('__name__') or '').strip()
            if not metric:
                continue
            observed_metrics.add(metric)
            metric_labels[metric].update(str(key) for key in row if key != '__name__')
            metric_series_count[metric] += 1
        return observed_metrics, dict(metric_labels), dict(metric_series_count)

    def _audit_query(
        self,
        definition: QueryDefinition,
        *,
        observed_metrics: set[str],
        metric_labels: dict[str, set[str]],
        metric_series_count: dict[str, int],
        execute_queries: bool,
    ) -> dict[str, Any]:
        missing_metrics = tuple(metric for metric in definition.required_metrics if metric not in observed_metrics)
        missing_labels = tuple(
            f'{metric}.{label}'
            for metric, labels in definition.required_labels
            for label in labels
            if label not in metric_labels.get(metric, set())
        )
        series_count = sum(metric_series_count.get(metric, 0) for metric in definition.required_metrics)

        status = 'ready'
        detail = 'Metric family, label schema, and query contract are available.'
        execution_state = 'not_run'
        execution_error: str | None = None

        if missing_metrics:
            status = 'blocked' if definition.readiness_tier == 'required' else 'unsupported'
            detail = f'Missing scoped metric family: {", ".join(missing_metrics)}.'
        elif missing_labels:
            status = 'blocked'
            detail = f'Missing required label schema: {", ".join(missing_labels)}.'
        elif execute_queries:
            try:
                payload = self.client.query(definition.expression)
            except PrometheusError as exc:
                status = 'blocked'
                execution_state = 'failed'
                execution_error = str(exc)
                detail = f'Registered PromQL query failed: {execution_error}'
            else:
                if not isinstance(payload, dict) or payload.get('status') != 'success':
                    status = 'blocked'
                    execution_state = 'failed'
                    detail = 'Registered PromQL query returned an unsuccessful response.'
                    result = []
                else:
                    result = (payload.get('data') or {}).get('result') or []
                if execution_state != 'failed':
                    if not isinstance(result, list) or not result:
                        status = 'no_data'
                        execution_state = 'no_data'
                        detail = 'Query executed successfully but returned no scoped samples.'
                    else:
                        execution_state = 'ready'
        else:
            execution_state = 'deferred'

        return {
            'key': definition.key,
            'label': _QUERY_LABELS.get(definition.key, definition.key.replace('_', ' ').replace('.', ' · ').title()),
            'domain': definition.domain,
            'domain_label': _DOMAIN_LABELS.get(definition.domain, definition.domain.replace('_', ' ').title()),
            'tier': definition.readiness_tier,
            'status': status,
            'detail': detail,
            'required_metrics': list(definition.required_metrics),
            'required_labels': [
                {'metric': metric, 'labels': list(labels)} for metric, labels in definition.required_labels
            ],
            'missing_metrics': list(missing_metrics),
            'missing_labels': list(missing_labels),
            'series_count': series_count,
            'required_history': definition.required_history,
            'expression': definition.expression,
            'execution_state': execution_state,
            'execution_error': execution_error,
        }

    @staticmethod
    def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {
            'total': len(items),
            'ready': sum(item['status'] == 'ready' for item in items),
            'no_data': sum(item['status'] == 'no_data' for item in items),
            'unsupported': sum(item['status'] == 'unsupported' for item in items),
            'blocked': sum(item['status'] == 'blocked' for item in items),
        }
        required = [item for item in items if item['tier'] == 'required']
        required_blocked = sum(item['status'] == 'blocked' for item in required)
        required_no_data = sum(item['status'] == 'no_data' for item in required)
        counts['required_total'] = len(required)
        counts['required_ready'] = sum(item['status'] == 'ready' for item in required)
        counts['required_blocked'] = required_blocked
        counts['required_no_data'] = required_no_data
        if required and required_blocked == len(required):
            counts['status'] = 'blocked'
        elif required_blocked or required_no_data:
            counts['status'] = 'partial'
        else:
            counts['status'] = 'ready'
        return counts

    @staticmethod
    def _domain_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            grouped[str(item['domain'])].append(item)

        rows: list[dict[str, Any]] = []
        for domain, domain_items in grouped.items():
            required = [item for item in domain_items if item['tier'] == 'required']
            blocked_required = sum(item['status'] == 'blocked' for item in required)
            no_data_required = sum(item['status'] == 'no_data' for item in required)
            if blocked_required or no_data_required:
                state = 'partial'
            elif any(item['status'] in {'blocked', 'unsupported', 'no_data'} for item in domain_items):
                state = 'partial'
            else:
                state = 'ready'
            rows.append(
                {
                    'domain': domain,
                    'label': _DOMAIN_LABELS.get(domain, domain.replace('_', ' ').title()),
                    'status': state,
                    'ready_count': sum(item['status'] == 'ready' for item in domain_items),
                    'total_count': len(domain_items),
                    'required_ready_count': sum(item['status'] == 'ready' for item in required),
                    'required_total_count': len(required),
                }
            )
        return rows
