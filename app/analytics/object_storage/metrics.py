from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.integrations.prometheus.query_profiles.object_storage_v1 import get_object_storage_query_expression
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


class ObjectStorageMetricsService:
    """Read Object Storage operational evidence through the canonical Prometheus consumer."""

    def __init__(self, consumer: PrometheusConsumer) -> None:
        self.consumer = consumer

    def instant(self, query_key: str) -> dict[str, Any]:
        return self.consumer.query(get_object_storage_query_expression(query_key))

    def range(self, query_key: str, time_range: str) -> dict[str, Any]:
        window, step = _TIME_WINDOWS.get(time_range, _TIME_WINDOWS['24h'])
        end = datetime.now(UTC)
        start = end - window
        return self.consumer.query_range(
            get_object_storage_query_expression(query_key),
            start.isoformat(),
            end.isoformat(),
            step,
        )
