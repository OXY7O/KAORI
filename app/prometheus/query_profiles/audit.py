from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.prometheus.capabilities import definition as capability_definition
from app.prometheus.exceptions import PrometheusError
from app.prometheus.query_profiles import PROFILE_KEY, list_queries


@dataclass(frozen=True)
class QueryCheckResult:
    key: str
    status: str
    message: str
    missing_metrics: tuple[str, ...] = ()
    missing_labels: tuple[str, ...] = ()
    deprecated: bool = False
    replacement_key: str | None = None


class PromQLProfileAuditor:
    """Validate the versioned PromQL profile against one configured endpoint."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def audit(self, *, execute_queries: bool = True) -> dict[str, Any]:
        definitions = list_queries()
        available_metrics = self._available_metric_names()
        namespaces = self.client.label_values('namespace').get('data') or []
        sample_namespace = namespaces[0] if namespaces else 'default'
        label_requirements = {
            metric
            for definition in definitions
            for metric, _labels in definition.required_labels
            if metric in available_metrics
        }
        metric_label_cache = self._labels_for_metrics(label_requirements)
        results: list[QueryCheckResult] = []

        for definition in definitions:
            missing_metrics = tuple(
                metric for metric in definition.required_metrics if metric not in available_metrics
            )
            missing_labels: list[str] = []
            if not missing_metrics and definition.required_labels:
                for metric, required_labels in definition.required_labels:
                    labels = metric_label_cache.get(metric, set())
                    missing_labels.extend(
                        f'{metric}.{label}' for label in required_labels if label not in labels
                    )

            status = 'ready'
            message = 'Required metrics and labels are available.'
            if missing_metrics:
                status = 'blocked'
                message = 'Required metrics are unavailable.'
            elif missing_labels:
                status = 'blocked'
                message = 'Required label schema is unavailable.'
            elif definition.is_deprecated:
                status = 'deprecated'
                message = 'Query is deprecated and must use its registered replacement.'
            elif execute_queries:
                expression = definition.expression.replace('$namespace', _escape_label_value(sample_namespace))
                response = self.client.query(expression)
                if response.get('status') != 'success':
                    status = 'blocked'
                    message = 'Prometheus rejected the query.'

            results.append(QueryCheckResult(
                key=definition.key,
                status=status,
                message=message,
                missing_metrics=missing_metrics,
                missing_labels=tuple(sorted(set(missing_labels))),
                deprecated=definition.is_deprecated,
                replacement_key=definition.replacement_key,
            ))

        retention = self.validate_retention(('24h', '7d', '30d', '60d'))
        blocked = sum(item.status == 'blocked' for item in results)
        deprecated = sum(item.status == 'deprecated' for item in results)
        domain_summary = self._domain_summary(definitions, results)
        blocked_details = self._blocked_details(definitions, results)
        capability_assessments = self._capability_assessments(
            available_metrics, metric_label_cache, retention, blocked_details
        )
        module_readiness = self._module_readiness(domain_summary)
        core_domains = {'app.prometheus', 'app.analytics.capacity', 'app.analytics.utilization'}
        critical_blocked = sum(
            item['blocked_count'] for domain, item in domain_summary.items() if domain in core_domains
        )
        return {
            'profile': PROFILE_KEY,
            'checked_at': datetime.now(UTC).isoformat(),
            'query_count': len(results),
            'ready_count': len(results) - blocked - deprecated,
            'blocked_count': blocked,
            'critical_blocked_count': critical_blocked,
            'deprecated_count': deprecated,
            'domain_summary': domain_summary,
            'blocked_details': blocked_details,
            'capability_assessments': capability_assessments,
            'available_capabilities': sorted(
                item['key'] for item in capability_assessments if item['status'] == 'available'
            ),
            'module_readiness': module_readiness,
            'retention': retention,
            'results': [asdict(item) for item in results],
        }

    def validate_retention(self, horizons: Iterable[str]) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        now = datetime.now(UTC)
        for horizon in horizons:
            delta = _parse_duration(horizon)
            sample_time = now - delta
            response = self.client.query_at('count(up)', sample_time.timestamp())
            rows = response.get('data', {}).get('result', []) if response.get('status') == 'success' else []
            output[horizon] = {
                'available': bool(rows),
                'sample_time': sample_time.isoformat(),
                'message': 'Historical samples found.' if rows else 'No historical samples found at this horizon.',
            }
        return output

    def _available_metric_names(self) -> set[str]:
        response = self.client.label_values('__name__')
        return set(response.get('data') or []) if response.get('status') == 'success' else set()

    def _labels_for_metrics(self, metrics: set[str]) -> dict[str, set[str]]:
        """Fetch recent label schemas in bounded batches instead of one request per query.

        Thanos Query can make unbounded /series calls expensive. Restricting discovery to
        the last 15 minutes and batching metric selectors keeps full validation finite.
        A failed batch is recorded as an empty schema and degrades only affected queries.
        """
        output = {metric: set() for metric in metrics}
        metric_list = sorted(metrics)
        now = datetime.now(UTC)
        start = (now - timedelta(minutes=15)).timestamp()
        end = now.timestamp()
        for offset in range(0, len(metric_list), 12):
            batch = metric_list[offset:offset + 12]
            try:
                response = self.client.series(batch, limit=500, start=start, end=end)
            except PrometheusError:
                continue
            rows = response.get('data') or [] if response.get('status') == 'success' else []
            for row in rows:
                metric = row.get('__name__')
                if metric in output:
                    output[metric].update(row.keys())
        return output

    def _capability_assessments(
        self,
        available_metrics: set[str],
        metric_labels: dict[str, set[str]],
        retention: dict[str, dict[str, Any]],
        blocked_details: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assessments: list[dict[str, Any]] = []

        def add(key: str, status: str, evidence: str) -> None:
            item = capability_definition(key)
            if item is None:
                return
            assessments.append({
                'key': item.key,
                'label': item.label,
                'status': status,
                'required_by': list(item.required_by),
                'impact': item.impact,
                'source_owner': item.source_owner,
                'recommendation': item.recommendation,
                'expected_signals': list(item.expected_signals),
                'validation_query': item.validation_query,
                'evidence': evidence,
            })

        add('instant_query', 'available', 'The configured endpoint accepted vector(1).')
        add('range_query', 'available', 'The Prometheus-compatible range query contract is expected and audited by the query profile.')

        identity = {'kube_node_info', 'kube_pod_info', 'kube_namespace_status_phase'}
        missing_identity = sorted(identity - available_metrics)
        add(
            'kubernetes_identity',
            'available' if not missing_identity else 'missing',
            'All Kubernetes identity metrics are queryable.' if not missing_identity else f"Missing metrics: {', '.join(missing_identity)}",
        )

        resource = {'kube_pod_container_resource_requests', 'kube_pod_container_resource_limits'}
        missing_resource = sorted(resource - available_metrics)
        add(
            'resource_requests_limits',
            'available' if not missing_resource else 'missing',
            'Request and limit metrics are queryable.' if not missing_resource else f"Missing metrics: {', '.join(missing_resource)}",
        )

        pvc = {'kubelet_volume_stats_capacity_bytes', 'kubelet_volume_stats_used_bytes', 'kubelet_volume_stats_available_bytes'}
        missing_pvc = sorted(pvc - available_metrics)
        add(
            'pvc_usage',
            'available' if not missing_pvc else 'missing',
            'PVC usage metrics are queryable.' if not missing_pvc else f"Missing metrics: {', '.join(missing_pvc)}",
        )

        filesystem_metrics = {'node_filesystem_size_bytes', 'node_filesystem_avail_bytes'}
        filesystem_present = filesystem_metrics.issubset(available_metrics)
        observed_labels = set().union(*(metric_labels.get(metric, set()) for metric in filesystem_metrics))
        canonical_labels = {'node', 'nodename', 'kubernetes_node'}
        if not filesystem_present:
            node_status = 'missing'
            node_evidence = 'node_filesystem_size_bytes or node_filesystem_avail_bytes is missing.'
        elif observed_labels & canonical_labels:
            node_status = 'available'
            node_evidence = f"Canonical identity label observed: {', '.join(sorted(observed_labels & canonical_labels))}."
        elif 'instance' in observed_labels:
            node_status = 'misconfigured'
            node_evidence = 'Only the instance label was observed; values may be IP:port and cannot be treated as canonical Kubernetes node names.'
        else:
            node_status = 'not_observed'
            node_evidence = 'Filesystem metrics exist, but no canonical node identity label was observed in the recent sample window.'
        add('node_filesystem_identity', node_status, node_evidence)

        history_ready = bool(retention.get('60d', {}).get('available'))
        add(
            'long_term_history',
            'available' if history_ready else 'missing',
            'Historical samples were found at 60 days.' if history_ready else 'No samples were found at the 60-day horizon.',
        )

        return assessments

    @staticmethod
    def _module_readiness(domain_summary: dict[str, dict[str, int]]) -> dict[str, dict[str, object]]:
        labels = {
            'app.prometheus': 'Kubernetes Overview',
            'app.analytics.utilization': 'Utilization Analytics',
            'app.analytics.capacity': 'Capacity Analytics',
            'app.analytics.storage': 'Storage Analytics',
            'app.analytics.workload': 'Workload Analytics',
            'app.analytics.forecast': 'Forecast',
            'app.analytics.top_consumers': 'Top Consumers',
        }
        output: dict[str, dict[str, object]] = {}
        for domain, values in domain_summary.items():
            blocked = values.get('blocked_count', 0)
            output[domain] = {
                'label': labels.get(domain, domain.replace('app.analytics.', '').replace('app.', '').replace('_', ' ').title()),
                'status': 'ready' if blocked == 0 else ('unavailable' if values.get('ready_count', 0) == 0 else 'degraded'),
                'ready_count': values.get('ready_count', 0),
                'query_count': values.get('query_count', 0),
                'blocked_count': blocked,
            }
        return output

    @staticmethod
    def _blocked_details(definitions: Sequence[Any], results: Sequence[QueryCheckResult]) -> list[dict[str, Any]]:
        """Return compact, user-facing evidence for checks that block profile coverage."""
        output: list[dict[str, Any]] = []
        for definition, result in zip(definitions, results, strict=True):
            if result.status != 'blocked':
                continue
            output.append({
                'key': result.key,
                'domain': definition.domain,
                'message': result.message,
                'missing_metrics': list(result.missing_metrics),
                'missing_labels': list(result.missing_labels),
            })
        return output

    @staticmethod
    def _domain_summary(definitions: Sequence[Any], results: Sequence[QueryCheckResult]) -> dict[str, dict[str, int]]:
        output: dict[str, dict[str, int]] = {}
        for definition, result in zip(definitions, results, strict=True):
            item = output.setdefault(definition.domain, {'query_count': 0, 'ready_count': 0, 'blocked_count': 0, 'deprecated_count': 0})
            item['query_count'] += 1
            if result.status == 'ready':
                item['ready_count'] += 1
            elif result.status == 'blocked':
                item['blocked_count'] += 1
            elif result.status == 'deprecated':
                item['deprecated_count'] += 1
        return output


def _parse_duration(value: str) -> timedelta:
    unit = value[-1]
    amount = int(value[:-1])
    if unit == 'h':
        return timedelta(hours=amount)
    if unit == 'd':
        return timedelta(days=amount)
    raise ValueError(f'Unsupported retention duration: {value}')


def _escape_label_value(value: str) -> str:
    return value.replace('\\', '\\\\').replace('\"', '\\"')
