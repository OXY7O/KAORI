from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

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
        metric_label_cache: dict[str, set[str]] = {}
        results: list[QueryCheckResult] = []

        for definition in definitions:
            missing_metrics = tuple(
                metric for metric in definition.required_metrics if metric not in available_metrics
            )
            missing_labels: list[str] = []
            if not missing_metrics and definition.required_labels:
                for metric, required_labels in definition.required_labels:
                    labels = metric_label_cache.setdefault(metric, self._labels_for_metric(metric))
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
        return {
            'profile': PROFILE_KEY,
            'checked_at': datetime.now(UTC).isoformat(),
            'query_count': len(results),
            'ready_count': len(results) - blocked - deprecated,
            'blocked_count': blocked,
            'deprecated_count': deprecated,
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

    def _labels_for_metric(self, metric: str) -> set[str]:
        response = self.client.series([metric], limit=20)
        rows = response.get('data') or [] if response.get('status') == 'success' else []
        labels: set[str] = set()
        for row in rows:
            labels.update(row.keys())
        return labels


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
