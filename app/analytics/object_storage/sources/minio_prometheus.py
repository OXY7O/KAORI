from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.analytics.shared.metrics import (
    MetricPoint,
    MetricsSourceError,
    MetricsSourceFailureKind,
    MetricsSourceIdentity,
)
from app.integrations.prometheus.exceptions import (
    PrometheusAuthenticationError,
    PrometheusConnectionError,
    PrometheusError,
    PrometheusQueryError,
)
from app.integrations.prometheus.query_profiles.object_storage_v1 import get_object_storage_query_expression
from app.models.object_storage import ObjectStorageSystem
from app.prometheus.consumer import PrometheusConsumer

_TIME_WINDOWS: dict[str, tuple[timedelta, str]] = {
    '1h': (timedelta(hours=1), '60s'),
    '6h': (timedelta(hours=6), '2m'),
    '12h': (timedelta(hours=12), '5m'),
    '24h': (timedelta(hours=24), '5m'),
    '7d': (timedelta(days=7), '30m'),
    '30d': (timedelta(days=30), '2h'),
    '60d': (timedelta(days=60), '4h'),
}


def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data')
    if not isinstance(data, dict):
        return []
    result = data.get('result')
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _number(value: object) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _vector_scalar(payload: dict[str, Any]) -> float | None:
    for item in _results(payload):
        value = item.get('value')
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return _number(value[1])
    return None


def _vector_by_label(payload: dict[str, Any], label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in _results(payload):
        metric = item.get('metric')
        value = item.get('value')
        if not isinstance(metric, dict) or not isinstance(value, (list, tuple)) or len(value) < 2:
            continue
        key = str(metric.get(label) or '').strip()
        number = _number(value[1])
        if key and number is not None:
            values[key] = number
    return values


def _matrix_points(payload: dict[str, Any]) -> list[MetricPoint]:
    rows = _results(payload)
    if not rows:
        return []
    values = rows[0].get('values')
    if not isinstance(values, list):
        return []
    points: list[MetricPoint] = []
    for value in values:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            continue
        timestamp = _number(value[0])
        number = _number(value[1])
        if timestamp is not None and number is not None:
            points.append({'timestamp': timestamp, 'value': number})
    return points


def _translate_error(exc: PrometheusError) -> MetricsSourceError:
    if isinstance(exc, PrometheusConnectionError):
        kind = MetricsSourceFailureKind.TRANSPORT
    elif isinstance(exc, PrometheusAuthenticationError):
        kind = MetricsSourceFailureKind.AUTHENTICATION
    elif isinstance(exc, PrometheusQueryError):
        kind = MetricsSourceFailureKind.QUERY
    else:
        kind = MetricsSourceFailureKind.CONFIGURATION
    return MetricsSourceError(str(exc), kind=kind, provider='prometheus')


class MinioPrometheusMetricsSource:
    """Translate KAORI MinIO metric semantics to Prometheus evidence."""

    def __init__(self, consumer: PrometheusConsumer) -> None:
        self._consumer = consumer

    @staticmethod
    def supports(system: ObjectStorageSystem) -> bool:
        """Return whether this adapter has a qualified metric profile for the asset provider."""
        return system.minio_connection is not None

    @classmethod
    def for_system(cls, system: ObjectStorageSystem) -> MinioPrometheusMetricsSource:
        if not cls.supports(system):
            raise MetricsSourceError(
                'Prometheus is bound, but no qualified Prometheus metric profile is registered for this Object Storage provider.',
                kind=MetricsSourceFailureKind.CONFIGURATION,
                provider='prometheus',
            )
        try:
            consumer = PrometheusConsumer.for_asset(
                scope_type='object_storage_system',
                scope_key=system.id,
                scope_name=system.name,
            )
        except PrometheusError as exc:
            raise _translate_error(exc) from exc
        return cls(consumer)

    @property
    def identity(self) -> MetricsSourceIdentity:
        profile = str(self._consumer.binding.validation_profile or '').strip()
        detail_parts = [self._consumer.config.name, 'MinIO metrics v2']
        if profile:
            detail_parts.append(profile)
        return MetricsSourceIdentity(
            provider='prometheus',
            provider_label='Prometheus',
            instance_name=self._consumer.config.name,
            detail=' · '.join(detail_parts),
        )

    def scalar(self, metric_key: str) -> float | None:
        try:
            payload = self._consumer.query(
                get_object_storage_query_expression(metric_key),
                retry_count=0,
            )
        except PrometheusError as exc:
            raise _translate_error(exc) from exc
        return _vector_scalar(payload)

    def vector(self, metric_key: str, label: str) -> dict[str, float]:
        try:
            payload = self._consumer.query(
                get_object_storage_query_expression(metric_key),
                retry_count=0,
            )
        except PrometheusError as exc:
            raise _translate_error(exc) from exc
        return _vector_by_label(payload, label)

    def trend(self, metric_key: str, time_range: str) -> list[MetricPoint]:
        window, step = _TIME_WINDOWS.get(time_range, _TIME_WINDOWS['24h'])
        end = datetime.now(UTC)
        start = end - window
        try:
            payload = self._consumer.query_range(
                get_object_storage_query_expression(metric_key),
                start.isoformat(),
                end.isoformat(),
                step,
                retry_count=0,
            )
        except PrometheusError as exc:
            raise _translate_error(exc) from exc
        return _matrix_points(payload)
