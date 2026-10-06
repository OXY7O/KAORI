#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise SystemExit(f'Missing Job Progress final-lock file: {relative}')
    return path.read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []

    component = read('app/templates/components/progress_bar.html')
    presentation = read('app/common/job_execution_presentation.py')
    service = read('app/platform_operations/jobs/service.py')
    execution = read('app/platform_operations/jobs/execution.py')
    jobs_readme = read('app/platform_operations/jobs/README.md')

    for required in (
        'macro job_progress(',
        '<div class="w-full min-w-0">',
        '{% macro notification_track_classes()',
        'h-1.5 w-full overflow-hidden rounded-full',
        '{% macro notification_indeterminate(',
        'style="width: {{ safe_value }}%"',
        'data-progress="{{ safe_value }}"',
        'transition-all duration-500 ease-out',
        "queued=job.progress_mode == 'queued'",
        '{% if queued %}',
        'w-1/4 rounded-full bg-kaori-primary/55',
    ):
        if required not in component:
            errors.append(f'Canonical progress component missing: {required}')

    for forbidden in (
        'w-1/3 rounded-full bg-kaori-primary/60',
        'progress_bar.determinate(',
    ):
        if forbidden in component:
            errors.append(f'Legacy Job Progress geometry/API remains: {forbidden}')

    for required in (
        "payload['_progress'] = metadata",
        "metadata['percent']",
        "metadata['stage']",
        "metadata['target']",
    ):
        if required not in service:
            errors.append(f'JobExecution reserved progress metadata missing: {required}')

    for required in (
        'percent: int | None = None',
        'stage: str | None = None',
        'target: str | None = None',
    ):
        if required not in execution:
            errors.append(f'Job execution context progress field missing: {required}')

    for required in (
        "'minio': 'MinIO'",
        "'kubernetes': 'Kubernetes'",
        "'metrics_source': 'Metrics Source'",
        "'alertmanager': 'Alertmanager'",
        "if raw.lower() == 'all':",
        "return 'All'",
        "if raw.lower() == 'global':",
        "return 'Global'",
        "if job.status == 'queued':\n        return 'Waiting'",
        "payload.get('_progress')",
        'provider_label = _provider_label(job.integration_type)',
        "'provider_label': _provider_label(job.integration_type)",
        "'progress_process': progress_process",
        "'progress_detail': progress_detail",
        'scope = _scope_label(raw_scope)',
    ):
        if required not in presentation:
            errors.append(f'Job identity/progress presentation missing: {required}')

    shared_surfaces = (
        'app/templates/platform_operations/jobs/configuration/_execution_activity.html',
        'app/templates/platform_operations/jobs/executions/partials/_active_jobs.html',
        'app/templates/platform_operations/jobs/executions/partials/_registry.html',
        'app/templates/platform_operations/jobs/executions/partials/_execution_details.html',
        'app/templates/platform_operations/notifications/components/_activity_center_items.html',
        'app/templates/reports/generated/detail.html',
    )
    for relative in shared_surfaces:
        source = read(relative)
        if 'progress_bar.job_progress' not in source:
            errors.append(f'{relative}: canonical job_progress renderer missing')
        if 'progress_bar.determinate' in source:
            errors.append(f'{relative}: legacy determinate renderer remains')

    notification_item = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    if '<div class="mt-2 w-full">{{ progress_bar.job_progress(' not in notification_item:
        errors.append('Notification Active Work must give Job Progress the full available track width')

    active_jobs = read('app/templates/platform_operations/jobs/executions/partials/_active_jobs.html')
    queue_activity = read('app/templates/platform_operations/jobs/executions/partials/_queue_activity.html')
    registry = read('app/templates/platform_operations/jobs/executions/partials/_registry.html')
    for source, required in (
        (active_jobs, "loading_bar.render('active-job-loading', label='Refreshing Active Work')"),
        (
            queue_activity,
            "loading_bar.render('job-queue-loading', label='Refreshing Queue Activity and Worker Readiness')",
        ),
        (registry, "loading_bar.render('job-execution-loading', label='Refreshing Job Execution Registry')"),
    ):
        if required not in source:
            errors.append(f'Jobs loading-bar contract missing: {required}')

    for required in (
        '## Job Progress Contract',
        'components/progress_bar.html::job_progress',
        'payload_json._progress',
    ):
        if required not in jobs_readme:
            errors.append(f'Job Progress v2 documentation missing: {required}')

    if errors:
        print('FAIL — KAORI Job Progress Final Lock v2')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Job Progress Final Lock v2')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
