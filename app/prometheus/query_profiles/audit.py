from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

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

    @staticmethod
    def _blocked_details(definitions: list[Any], results: list[QueryCheckResult]) -> list[dict[str, Any]]:
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
    def _domain_summary(definitions: list[Any], results: list[QueryCheckResult]) -> dict[str, dict[str, int]]:
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
