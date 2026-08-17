from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from hashlib import sha256
from threading import Lock
from time import monotonic, sleep
from typing import Any

from flask import current_app
from sqlalchemy import text

from app.alert_sources.providers.alertmanager.consumer import KUBERNETES_CLUSTER_SCOPE
from app.alert_sources.providers.alertmanager.resolver import resolve_alertmanager_sources
from app.analytics.kubernetes.materialization.catalog import (
    canonical_parameters,
    get_dataset,
    source_binding_capabilities,
    source_technical_capabilities,
)
from app.analytics.kubernetes.materialization.errors import AnalyticsSourceBusyError
from app.extensions.db import db
from app.metrics_sources.resolver import resolve_metrics_sources

_fallback_locks: dict[str, Lock] = {}


def _advisory_lock_key(value: str) -> int:
    digest = sha256(value.encode('utf-8')).digest()[:8]
    return int.from_bytes(digest, byteorder='big', signed=True)


def _provider_lock_names(
    *,
    dataset_key: str,
    cluster_id: str,
    parameters: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Resolve stable provider locks without making resolution a new failure point.

    Alert materialization can read Alertmanager and Metrics Source in one dataset
    (Alertmanager alerts plus Metrics Source anomaly candidates). Acquiring every
    selected provider lock in sorted order prevents those optional queries from
    bypassing the same-source concurrency boundary used by other analytics jobs.
    """

    dataset = get_dataset(dataset_key)
    normalized = canonical_parameters(dataset_key, parameters)
    lock_names: set[str] = set()
    try:
        if dataset.source_kind == 'metrics_source':
            resolution = resolve_metrics_sources(
                scope_type=KUBERNETES_CLUSTER_SCOPE,
                scope_key=str(cluster_id),
                required_binding_capabilities=source_binding_capabilities(dataset_key),
                required_technical_capabilities=source_technical_capabilities(dataset_key),
            )
            selected = resolution.selected
            if selected is not None:
                lock_names.add(f'analytics-source:metrics_source:{selected.instance.id}')
        elif dataset.source_kind == 'alert':
            requested_source = normalized.get('source', 'auto').lower()
            if requested_source in {'auto', 'alertmanager'}:
                alertmanager = resolve_alertmanager_sources(
                    scope_type=KUBERNETES_CLUSTER_SCOPE,
                    scope_key=str(cluster_id),
                )
                if alertmanager.selected is not None:
                    lock_names.add(f'analytics-source:alertmanager:{alertmanager.selected.instance.id}')
            if requested_source in {'auto', 'metrics_source'}:
                metrics_source = resolve_metrics_sources(
                    scope_type=KUBERNETES_CLUSTER_SCOPE,
                    scope_key=str(cluster_id),
                    required_binding_capabilities=('metrics',),
                    required_technical_capabilities=('instant_query',),
                )
                if metrics_source.selected is not None:
                    lock_names.add(f'analytics-source:metrics_source:{metrics_source.selected.instance.id}')
    except Exception:
        current_app.logger.warning(
            'Could not resolve provider-specific analytics query locks; using cluster fallback.',
            exc_info=True,
            extra={
                'dataset_key': dataset_key,
                'cluster_id': str(cluster_id),
                'source_kind': dataset.source_kind,
            },
        )
    if not lock_names:
        lock_names.add(f'analytics-source:{dataset.source_kind}:{cluster_id}')
    return tuple(sorted(lock_names))


def _timeout_seconds() -> int:
    try:
        return max(
            int(current_app.config.get('ANALYTICS_SOURCE_LOCK_TIMEOUT_SECONDS', 900)),
            1,
        )
    except (TypeError, ValueError):
        return 900


@contextmanager
def analytics_source_lock(
    *,
    dataset_key: str,
    cluster_id: str,
    parameters: Mapping[str, Any] | None,
) -> Iterator[int]:
    """Serialize heavy analytics requests by selected provider instance.

    Multiple clusters can share one Metrics Source endpoint and an alert
    dataset can query both Alertmanager and Metrics Source. Locks are acquired in a
    deterministic order, preventing parallel workers from overloading the same
    provider while still allowing unrelated providers to run concurrently.

    The yielded value is the total wait duration in milliseconds.
    """

    lock_names = _provider_lock_names(
        dataset_key=dataset_key,
        cluster_id=cluster_id,
        parameters=parameters,
    )
    timeout_seconds = _timeout_seconds()
    started = monotonic()
    engine = db.engine

    if engine.dialect.name == 'postgresql':
        connection = engine.connect()
        acquired_keys: list[int] = []
        try:
            deadline = started + timeout_seconds
            for lock_name in lock_names:
                lock_key = _advisory_lock_key(lock_name)
                acquired = False
                while monotonic() < deadline:
                    acquired = bool(
                        connection.execute(
                            text('SELECT pg_try_advisory_lock(:lock_key)'),
                            {'lock_key': lock_key},
                        ).scalar()
                    )
                    if acquired:
                        acquired_keys.append(lock_key)
                        break
                    sleep(0.25)
                if not acquired:
                    raise AnalyticsSourceBusyError(
                        f'Provider query slot {lock_name} was not available within {timeout_seconds} seconds.'
                    )
            yield max(int((monotonic() - started) * 1000), 0)
        finally:
            try:
                for lock_key in reversed(acquired_keys):
                    connection.execute(
                        text('SELECT pg_advisory_unlock(:lock_key)'),
                        {'lock_key': lock_key},
                    )
            finally:
                connection.close()
        return

    acquired_locks: list[Lock] = []
    try:
        deadline = started + timeout_seconds
        for lock_name in lock_names:
            remaining = max(deadline - monotonic(), 0)
            lock = _fallback_locks.setdefault(lock_name, Lock())
            if not lock.acquire(timeout=remaining):
                raise AnalyticsSourceBusyError(
                    f'Provider query slot {lock_name} was not available within {timeout_seconds} seconds.'
                )
            acquired_locks.append(lock)
        yield max(int((monotonic() - started) * 1000), 0)
    finally:
        for lock in reversed(acquired_locks):
            lock.release()
