#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []
    required_files = (
        'app/platform_operations/overview/__init__.py',
        'app/platform_operations/overview/routes.py',
        'app/platform_operations/overview/presentation.py',
        'app/templates/platform_operations/overview/index.html',
        'docs/design/KAORI_PLATFORM_OPERATIONS_OVERVIEW_LOCK_V1.md',
        'docs/design/KAORI_PLATFORM_OPERATIONS_OVERVIEW_LOCK_V1_1.md',
        'docs/design/audits/KAORI_PLATFORM_OPERATIONS_OVERVIEW_FINAL_LOCK_AUDIT_2026_08_08.md',
        'docs/design/audits/KAORI_PLATFORM_OPERATIONS_OVERVIEW_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md',
    )
    for relative in required_files:
        if not (ROOT / relative).exists():
            errors.append(f'missing Overview lock artifact: {relative}')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    routes = read('app/platform_operations/overview/routes.py')
    presentation = read('app/platform_operations/overview/presentation.py')
    template = read('app/templates/platform_operations/overview/index.html')
    menu = read('app/templates/components/navigation/platform_operations_menu.html')
    lifecycle_presentation = read('app/platform_operations/data_lifecycle/presentation.py')
    kubernetes_presentation = read('app/platform_operations/kubernetes/presentation.py')

    for required in (
        '@any_permission_required(',
        "'jobs.view'",
        "'platform_operations.view_data_lifecycle'",
        "'kubernetes_secrets.manage_reveal'",
    ):
        if required not in routes:
            errors.append(f'Overview permission contract missing: {required}')

    for required in (
        'build_job_execution_status_context()',
        'build_data_lifecycle_overview_summary()',
        'build_kubernetes_administration_summary()',
    ):
        if required not in presentation:
            errors.append(f'Overview projection contract missing: {required}')

    for forbidden in (
        'inspect_celery_topology',
        'get_queue_readiness',
        'build_storage_profile',
        'preview_retention',
        'list_namespace',
        'read_namespace',
        'enqueue_canonical_job',
    ):
        if forbidden in presentation:
            errors.append(f'Overview must remain lightweight/read-only: {forbidden}')

    for required in (
        'Platform Overview',
        'Platform Posture',
        'Workspace Posture',
        'Operating Boundaries',
        'Read-only overview; changes stay in each workspace.',
        'components/page_hero.html',
        'components/table_label.html',
        'components/operational_section_card.html',
        'components/section_link_button.html',
        'table_label.status_indicator_label',
        'section_link_button.render',
        'lg:grid-cols-3',
    ):
        if required not in template:
            errors.append(f'Overview UI contract missing: {required}')
    for forbidden in ('hx-post=', '<form', 'type="submit"', 'role="tablist"'):
        if forbidden in template:
            errors.append(f'Overview must remain navigation-only and use the compact v1.1 layout: {forbidden}')

    if not (
        menu.index('Overview')
        < menu.index('Jobs &amp; Executions')
        < menu.index('Data Lifecycle')
        < menu.index('K8s Administration')
    ):
        errors.append('Platform Operations navigation order drifted')

    for required in (
        'DataLifecyclePolicy.query',
        'ArchiveArtifact.query',
        "JobExecution.job_type == 'data_lifecycle'",
    ):
        if required not in lifecycle_presentation:
            errors.append(f'Data Lifecycle overview summary is not DB-backed: {required}')
    for forbidden in ('build_storage_profile(', 'get_queue_readiness(', 'preview_retention('):
        summary = lifecycle_presentation.split('def build_data_lifecycle_overview_summary()', 1)[-1]
        if forbidden in summary:
            errors.append(f'Data Lifecycle Overview projection must not probe runtime dependencies: {forbidden}')

    for required in ('Cluster.query', 'cluster_reveal_readiness', 'SecretRevealNamespacePolicy.query'):
        if required not in kubernetes_presentation:
            errors.append(f'Kubernetes Administration shared summary missing: {required}')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print('PASS — KAORI Platform Operations Overview Final Lock v1.1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
