#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    'app/platform_operations/data_lifecycle/__init__.py',
    'app/platform_operations/data_lifecycle/routes.py',
    'app/platform_operations/data_lifecycle/service.py',
    'app/platform_operations/data_lifecycle/presentation.py',
    'app/platform_operations/data_lifecycle/README.md',
    'app/templates/platform_operations/data_lifecycle/index.html',
    'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html',
    'app/templates/platform_operations/data_lifecycle/partials/_storage.html',
    'app/templates/platform_operations/data_lifecycle/partials/_history.html',
    'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1.md',
    'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_1.md',
    'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_2.md',
    'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_AUDIT_2026_08_08.md',
    'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md',
    'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md',
    'migrations/versions/20260808_data_lifecycle_platform_operations.py',
    'app/settings/data_lifecycle_compat.py',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f'missing Data Lifecycle lock artifact: {relative}')

    if (ROOT / 'app/templates/settings/data_lifecycle').exists():
        errors.append('legacy Settings Data Lifecycle templates must remain deleted')
    if (ROOT / 'app/settings/data_lifecycle').exists():
        errors.append('legacy Settings Data Lifecycle package must remain deleted; compatibility belongs in data_lifecycle_compat.py')

    platform_init = read('app/platform_operations/__init__.py')
    for required in (
        'from app.platform_operations.data_lifecycle import bp as data_lifecycle_bp',
        "bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')",
    ):
        if required not in platform_init:
            errors.append(f'Platform Operations Data Lifecycle registration missing: {required}')

    routes = read('app/platform_operations/data_lifecycle/routes.py')
    for required in (
        "Blueprint('data_lifecycle'",
        "@permission_required('platform_operations.view_data_lifecycle')",
        "@permission_required('platform_operations.manage_data_lifecycle')",
        "@permission_required('platform_operations.export_data_lifecycle')",
        "'platform_operations/data_lifecycle/index.html'",
        "'platform_operations/data_lifecycle/partials/_domain_workspace.html'",
        "'platform_operations/data_lifecycle/partials/_history.html'",
    ):
        if required not in routes:
            errors.append(f'canonical Platform Operations route contract missing: {required}')
    if 'settings.data_lifecycle' in routes or 'settings/data_lifecycle' in routes:
        errors.append('canonical Data Lifecycle routes must not depend on Settings ownership')

    service = read('app/platform_operations/data_lifecycle/service.py')
    for required in (
        'enqueue_canonical_job(',
        "job_type='data_lifecycle'",
        "action_url=url_for('jobs.executions')",
        'verify_archive_artifact(archive_id)',
    ):
        if required not in service:
            errors.append(f'Data Lifecycle service boundary missing: {required}')
    for forbidden in ('.delay(', '.apply_async(', 'send_task('):
        if forbidden in service:
            errors.append(f'Data Lifecycle must not bypass canonical job dispatch: {forbidden}')

    compatibility = read('app/settings/data_lifecycle_compat.py')
    for required in (
        "redirect(url_for(endpoint, **values), code=302)",
        "redirect(url_for(endpoint, **values), code=308)",
        "platform_operations.data_lifecycle.index",
        "platform_operations.data_lifecycle.save_policy",
        "platform_operations.data_lifecycle.run",
        "platform_operations.data_lifecycle.verify",
        "platform_operations.data_lifecycle.download",
    ):
        if required not in compatibility:
            errors.append(f'legacy Settings redirect contract missing: {required}')
    for forbidden in ('render_template', 'app.retention', 'enqueue_canonical_job', 'record_operational_activity'):
        if forbidden in compatibility:
            errors.append(f'legacy Settings compatibility route regained ownership: {forbidden}')

    index = read('app/templates/platform_operations/data_lifecycle/index.html')
    for required in (
        'components/framed_workspace_tabs.html',
        'framed_workspace_tabs.render(',
        "('policies', 'Retention Policies', 'sliders-horizontal')",
        "('history', 'Archive History', 'history')",
        "('storage', 'Archive Storage', 'hard-drive')",
        'Execution Boundary',
        "url_for('jobs.executions')",
    ):
        if required not in index:
            errors.append(f'Data Lifecycle workspace contract missing: {required}')
    for forbidden in ('role="tablist"', 'Planned Domains', 'bg-white', 'settings.data_lifecycle'):
        if forbidden in index:
            errors.append(f'Data Lifecycle workspace contains obsolete presentation debt: {forbidden}')
    expected_tabs = "[('policies', 'Retention Policies', 'sliders-horizontal'), ('history', 'Archive History', 'history'), ('storage', 'Archive Storage', 'hard-drive')]"
    if expected_tabs not in index or "tabs: ['policies', 'history', 'storage']" not in index:
        errors.append('Data Lifecycle tab order must be Retention Policies → Archive History → Archive Storage')
    if 'Only approved lifecycle domains are manageable.' not in index:
        errors.append('Data Lifecycle managed-domain helper copy drifted from the compact lock')

    domain_workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    storage = read('app/templates/platform_operations/data_lifecycle/partials/_storage.html')
    for required in (
        'components/loading_bar.html',
        "loading_bar.render('data-lifecycle-policy-loading'",
        'Changing retention days only changes eligibility; it does not run a job immediately.',
        'Requires Policy enabled + Scheduled execution.',
        'Transient failures retry once; exhausted failures require manual retry.',
        'Queue {{ lifecycle.queue_name }} · {{ lifecycle.worker.label }}.',
    ):
        if required not in domain_workspace:
            errors.append(f'Retention Policies operational contract missing: {required}')
    if 'notification-progress-indeterminate' in domain_workspace:
        errors.append('Retention Policies must use the shared KAORI loading bar, not the legacy notification progress segment')

    for required in (
        'Lifecycle Coverage',
        'Records covered by this retention, archive, and cleanup policy.',
        'Coverage:',
        'Excluded:',
    ):
        if required not in domain_workspace:
            errors.append(f'Data Lifecycle v1.2 coverage presentation missing: {required}')

    retention_presentation = read('app/retention/presentation.py')
    for required in (
        "'label': 'Activity Audit Table'",
        "'label': 'Notification Center'",
        "'label': 'Authentication Audit'",
        "'label': 'Kubernetes'",
        "'label': 'Prometheus'",
        "'label': 'Alertmanager'",
        'Future integrations using IntegrationRuntimeObservation inherit the same lifecycle boundary.',
        'Transient toasts are not persisted and therefore are not lifecycle-managed.',
    ):
        if required not in retention_presentation:
            errors.append(f'Data Lifecycle v1.2 coverage semantics missing: {required}')

    runtime_domain = read('app/retention/domains/runtime_observation.py')
    if 'IntegrationRuntimeObservation.query.filter(' not in runtime_domain:
        errors.append('Runtime Observation archive domain must read the canonical integration runtime model')
    if "IntegrationRuntimeObservation.provider ==" in runtime_domain or 'filter_by(provider=' in runtime_domain:
        errors.append('Runtime Observation lifecycle must remain provider-neutral; do not split Kubernetes/Prometheus/Alertmanager retention')

    activity_domain = read('app/retention/domains/operational_activity.py')
    if 'Notification.query.filter(Notification.id.in_(record_ids))' not in activity_domain:
        errors.append('Operational Activity lifecycle must continue cleaning the canonical Notification source table')
    if 'deck_visible' in activity_domain:
        errors.append('Operational Activity retention must not filter by deck visibility; audit-only and user notifications share one lifecycle')

    for required in (
        'Archive Target Contract',
        'Execution Contract',
        'Storage Readiness',
        'Worker Readiness',
        'Last Verified',
        'Archive-First Safety Boundary',
        'Freeze Boundary',
        'Verify Evidence',
        'Storage Interpretation',
        'Production uses the dedicated maintenance worker service.',
    ):
        if required not in storage:
            errors.append(f'Archive Storage operational evidence contract missing: {required}')

    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')
    for required in (
        'Archive History',
        "{{ 'Archive' if pager.total == 1 else 'Archives' }}",
        '<span class="text-xs font-semibold text-content-secondary">Rows</span>',
        'components/loading_bar.html',
        "loading_bar.render('data-lifecycle-history-loading'",
        'aria-label="Rows Per Page"',
        "current_user.has_permission('platform_operations.export_data_lifecycle')",
        "current_user.has_permission('platform_operations.manage_data_lifecycle')",
    ):
        if required not in history:
            errors.append(f'Archive History standard missing: {required}')
    if 'Lifecycle Execution History' in history:
        errors.append('Archive evidence must not be labeled as a second execution registry')
    if 'notification-progress-indeterminate' in history:
        errors.append('Archive History must use the shared KAORI loading bar')

    menu = read('app/templates/components/navigation/platform_operations_menu.html')
    settings_menu = read('app/templates/components/navigation/settings_menu.html')
    for required in (
        "current_user.has_permission('platform_operations.view_data_lifecycle')",
        "url_for('platform_operations.data_lifecycle.index')",
        'Data Lifecycle',
    ):
        if required not in menu:
            errors.append(f'Platform Operations navigation missing: {required}')
    if menu.find('Jobs &amp; Executions') > menu.find('Data Lifecycle') or menu.find('Data Lifecycle') > menu.find('Kubernetes Administration'):
        errors.append('Platform Operations navigation order must be Jobs & Executions → Data Lifecycle → Kubernetes Administration')
    if 'Data Lifecycle' in settings_menu or 'data_lifecycle' in settings_menu:
        errors.append('Settings navigation must not expose Data Lifecycle')

    breadcrumb = read('app/common/navigation.py')
    if "endpoint.startswith('platform_operations.data_lifecycle.')" not in breadcrumb:
        errors.append('Data Lifecycle breadcrumb must resolve under Platform Operations')

    defaults = read('app/rbac/defaults.py')
    dependencies = read('app/rbac/service.py')
    for key in (
        'platform_operations.view_data_lifecycle',
        'platform_operations.manage_data_lifecycle',
        'platform_operations.export_data_lifecycle',
    ):
        if key not in defaults:
            errors.append(f'RBAC defaults missing canonical Data Lifecycle permission: {key}')
    for old in (
        'settings.view_data_lifecycle',
        'settings.manage_data_lifecycle',
        'settings.export_data_lifecycle',
    ):
        if old in defaults or old in dependencies:
            errors.append(f'living RBAC code must not retain old Settings permission key: {old}')

    migration = read('migrations/versions/20260808_data_lifecycle_platform_operations.py')
    for required in (
        "down_revision = '20260805_notification_deck_v2'",
        "'settings.view_data_lifecycle'",
        "'platform_operations.view_data_lifecycle'",
        "'settings.manage_data_lifecycle'",
        "'platform_operations.manage_data_lifecycle'",
        "'settings.export_data_lifecycle'",
        "'platform_operations.export_data_lifecycle'",
        "module='operations'",
    ):
        if required not in migration:
            errors.append(f'Data Lifecycle ownership migration missing: {required}')

    activity = read('app/templates/notifications/activity.html')
    runtime_history = read('app/templates/integrations/partials/_runtime_history.html')
    retention_tasks = read('app/retention/tasks.py')
    for source_name, source in (
        ('Activity Audit', activity),
        ('Integration Runtime', runtime_history),
    ):
        if 'platform_operations.data_lifecycle.index' not in source:
            errors.append(f'{source_name} must link to Platform Operations Data Lifecycle')
    if '/platform-operations/data-lifecycle/?tab=history' not in retention_tasks:
        errors.append('retention worker notifications must link to canonical Platform Operations Data Lifecycle URL')
    for required in (
        '_is_retryable_retention_error',
        'RETENTION_RETRY_DELAY_SECONDS',
        'execution.retrying(',
        'self.retry(exc=exc, countdown=retry_delay, max_retries=1)',
    ):
        if required not in retention_tasks:
            errors.append(f'retention bounded retry contract missing: {required}')

    quality_gate = read('scripts/quality_gate.sh')
    if 'verify_data_lifecycle_final_lock.py' not in quality_gate:
        errors.append('Data Lifecycle final lock verifier must run in quality_gate.sh')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Data Lifecycle Final Lock v1.2 passed: Platform Operations owns route, template, RBAC, navigation, '
        'feedback and presentation boundaries; Settings is redirect-only; archive-first retention remains shared; '
        'Jobs & Executions remains canonical runtime evidence; Lifecycle Coverage explicitly maps Activity Audit, persistent '
        'Notification Center records, authentication audit, and provider-neutral Kubernetes/Prometheus/Alertmanager '
        'runtime observations; shared tabs, dark-mode-safe surfaces, Archive History pagination and compatibility migration are frozen.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
