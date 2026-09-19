#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

_REQUIRED_TASKS = {
    'app.reports.jobs.tasks.generate_report_job',
    'app.reports.schedules.tasks.run_report_schedule_job',
}


def _load_celery_app() -> Any:
    root = Path(__file__).resolve().parents[1]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return import_module('celery_worker').celery_app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Verify that a live KAORI Reports worker consumes the configured queue.',
    )
    parser.add_argument(
        '--queue',
        default=(os.getenv('REPORTS_CELERY_QUEUE', 'reports').strip() or 'reports'),
        help='Reports queue name. Defaults to REPORTS_CELERY_QUEUE or reports.',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=2.0,
        help='Celery inspection timeout in seconds.',
    )
    return parser.parse_args()


def _registered_task_names(values: list[Any] | None) -> set[str]:
    names: set[str] = set()
    for value in values or []:
        name = str(value or '').strip()
        if not name:
            continue
        names.add(name.split(' ', 1)[0])
    return names


def main() -> int:
    args = _parse_args()
    queue_name = str(args.queue).strip()
    celery_app = _load_celery_app()
    inspector = celery_app.control.inspect(timeout=max(float(args.timeout), 0.1))

    queue_map = inspector.active_queues() or {}
    registered_map = inspector.registered() or {}
    queue_workers = sorted(
        worker_name
        for worker_name, queues in queue_map.items()
        if queue_name in {str(queue.get('name') or '').strip() for queue in queues or []}
    )

    if not queue_workers:
        responding_workers = sorted(set(queue_map) | set(registered_map))
        detail = (
            f'Responding workers: {", ".join(responding_workers)}.'
            if responding_workers
            else 'No Celery worker responded.'
        )
        print(
            f'FAILED: no worker consumes the {queue_name!r} Reports queue. {detail}',
            file=sys.stderr,
        )
        return 1

    missing_by_worker: dict[str, list[str]] = {}
    for worker_name in queue_workers:
        registered_tasks = _registered_task_names(registered_map.get(worker_name))
        missing = sorted(_REQUIRED_TASKS - registered_tasks)
        if missing:
            missing_by_worker[worker_name] = missing

    if missing_by_worker:
        for worker_name, missing in missing_by_worker.items():
            print(
                f'FAILED: {worker_name} consumes {queue_name!r} but is missing tasks: {", ".join(missing)}',
                file=sys.stderr,
            )
        return 1

    print(f'PASS — KAORI Reports Worker Runtime · {len(queue_workers)} worker(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
