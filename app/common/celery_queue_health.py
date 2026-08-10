from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import Any

from flask import current_app

_TOPOLOGY_CACHE_LOCK = Lock()
_TOPOLOGY_CACHE: tuple[float, dict[str, Any]] | None = None


def _copy_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        **snapshot,
        'worker_names': list(snapshot.get('worker_names') or []),
        'worker_queues': {
            str(worker): list(queues or []) for worker, queues in dict(snapshot.get('worker_queues') or {}).items()
        },
    }


def inspect_celery_topology(
    *,
    timeout_seconds: float = 0.5,
    cache_ttl_seconds: float = 8.0,
) -> dict[str, Any]:
    """Return one short-lived Celery worker/queue topology snapshot.

    UI callers share this snapshot so navigation polling, Reports workspaces, and
    operational pages do not broadcast a separate Celery inspection request for
    every queue or every rendered card.
    """

    global _TOPOLOGY_CACHE

    now = monotonic()
    with _TOPOLOGY_CACHE_LOCK:
        cached = _TOPOLOGY_CACHE
        if cached is not None and now - cached[0] < max(cache_ttl_seconds, 0.0):
            return _copy_snapshot(cached[1])

    celery_app = current_app.extensions.get('celery')
    if celery_app is None:
        snapshot = {
            'status': 'unavailable',
            'worker_names': [],
            'worker_queues': {},
            'detail': 'Celery is not initialized in the KAORI web runtime.',
            'error_type': None,
        }
    else:
        try:
            inspector = celery_app.control.inspect(timeout=max(timeout_seconds, 0.1))
            queue_map = inspector.active_queues() or {}
            if not queue_map:
                ping_map = inspector.ping() or {}
                queue_map = {name: [] for name in ping_map}

            worker_queues = {
                str(worker_name): sorted(
                    {
                        str(queue.get('name') or '').strip()
                        for queue in queues or []
                        if str(queue.get('name') or '').strip()
                    }
                )
                for worker_name, queues in queue_map.items()
            }
            worker_names = sorted(worker_queues)
            snapshot = {
                'status': 'online' if worker_names else 'offline',
                'worker_names': worker_names,
                'worker_queues': worker_queues,
                'detail': (
                    f'{len(worker_names)} Celery worker(s) responded to topology inspection.'
                    if worker_names
                    else 'No Celery worker responded to topology inspection.'
                ),
                'error_type': None,
            }
        except Exception as exc:  # pragma: no cover - broker/runtime dependent
            current_app.logger.warning('Could not inspect Celery worker topology: %s', exc)
            snapshot = {
                'status': 'unknown',
                'worker_names': [],
                'worker_queues': {},
                'detail': f'Worker topology inspection failed with {type(exc).__name__}.',
                'error_type': type(exc).__name__,
            }

    with _TOPOLOGY_CACHE_LOCK:
        _TOPOLOGY_CACHE = (now, _copy_snapshot(snapshot))
    return _copy_snapshot(snapshot)


def get_queue_readiness(
    queue_name: str,
    *,
    topology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Present whether at least one inspected worker consumes ``queue_name``."""

    normalized_queue = str(queue_name or '').strip()
    snapshot = topology or inspect_celery_topology()
    worker_queues = dict(snapshot.get('worker_queues') or {})
    worker_names = sorted(str(name) for name in snapshot.get('worker_names') or [])
    queue_workers = sorted(
        worker_name
        for worker_name, queues in worker_queues.items()
        if normalized_queue in {str(queue) for queue in queues or []}
    )
    topology_status = str(snapshot.get('status') or 'unknown')

    if queue_workers:
        return {
            'status': 'online',
            'label': 'Online',
            'tone': 'normal',
            'icon': 'circle-check',
            'ready': True,
            'queue_name': normalized_queue,
            'worker_count': len(queue_workers),
            'worker_names': queue_workers,
            'description': (f'{len(queue_workers)} worker(s) are listening on the {normalized_queue} queue.'),
            'show_warning': False,
        }

    if topology_status == 'online':
        return {
            'status': 'queue_mismatch',
            'label': 'Worker Missing',
            'tone': 'warning',
            'icon': 'triangle-alert',
            'ready': False,
            'queue_name': normalized_queue,
            'worker_count': 0,
            'worker_names': worker_names,
            'description': (f'Celery workers responded, but none are listening on the {normalized_queue} queue.'),
            'show_warning': True,
        }

    if topology_status in {'offline', 'unavailable'}:
        return {
            'status': topology_status,
            'label': 'Offline',
            'tone': 'critical',
            'icon': 'circle-x',
            'ready': False,
            'queue_name': normalized_queue,
            'worker_count': 0,
            'worker_names': [],
            'description': (f'No worker is available for the {normalized_queue} queue. Queued jobs cannot start.'),
            'show_warning': True,
        }

    return {
        'status': 'unknown',
        'label': 'Unknown',
        'tone': 'unknown',
        'icon': 'circle-help',
        'ready': False,
        'queue_name': normalized_queue,
        'worker_count': 0,
        'worker_names': [],
        'description': (f'KAORI could not verify a worker for the {normalized_queue} queue.'),
        'show_warning': True,
    }
