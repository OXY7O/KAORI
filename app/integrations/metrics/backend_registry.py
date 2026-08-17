from __future__ import annotations

from typing import Any, Protocol

from app.integrations.metrics.exceptions import MetricsSourceError
from app.models.metrics_source import MetricsSource


class MetricsQuerySession(Protocol):
    def execute(self, operation: str, expression: str, **kwargs: Any) -> dict[str, Any]: ...


class MetricsBackendAdapter(Protocol):
    key: str

    def request_path(self, operation: str) -> str | None: ...

    def execute(self, operation: str, instance: MetricsSource, **kwargs: Any) -> Any: ...


_BACKENDS: dict[str, MetricsBackendAdapter] = {}


def register_metrics_backend(adapter: MetricsBackendAdapter) -> None:
    key = str(adapter.key or '').strip().lower()
    if not key:
        raise ValueError('Metrics backend adapter key is required.')
    if key in _BACKENDS:
        raise ValueError(f'Metrics backend adapter {key!r} is already registered.')
    _BACKENDS[key] = adapter


def metrics_backend_for(instance: MetricsSource) -> MetricsBackendAdapter:
    key = str(instance.adapter_key or '').strip().lower()
    try:
        return _BACKENDS[key]
    except KeyError as exc:
        raise MetricsSourceError(f'No metrics backend adapter is registered for {key!r}.') from exc


def metrics_backend_request_path(instance: MetricsSource, operation: str) -> str | None:
    return metrics_backend_for(instance).request_path(operation)
