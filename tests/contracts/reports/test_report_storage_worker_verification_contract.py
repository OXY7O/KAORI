from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_manual_storage_verification_is_dispatched_from_web_to_canonical_worker_job() -> None:
    routes = read('app/reports/storage/routes.py')
    jobs = read('app/reports/storage/jobs.py')

    assert 'enqueue_report_storage_verification' in routes
    assert 'verify_active_report_storage' not in routes
    assert 'requested_by_user_id=int(current_user.id)' in routes
    assert 'ReportStorageVerificationEnqueueError' in routes
    assert "'Report Storage Verification Queued'" in routes

    assert 'enqueue_canonical_job(' in jobs
    assert 'verify_report_storage_task' in jobs
    assert "job_type='report_storage'" in jobs
    assert "operation='verify_backend'" in jobs
    assert "scope_type='report_storage_backend'" in jobs
    assert "resource_group=f'report-storage:{backend_name}'" in jobs
    assert 'require_registered_worker=True' in jobs
    assert "REPORT_STORAGE_HEALTH_CELERY_QUEUE" in jobs


def test_storage_verification_worker_owns_network_probe_and_sanitizes_user_evidence() -> None:
    tasks = read('app/reports/storage/tasks.py')

    assert "name='app.reports.storage.tasks.verify_report_storage_task'" in tasks
    assert 'verify_active_report_storage()' in tasks
    assert 'JobExecutionContext' in tasks
    assert "logger.exception('Report storage verification worker failed.')" in tasks
    assert "lifecycle.fail(public_detail, error_code='report_storage_verification_failed')" in tasks
    assert 'raise ReportStorageConfigurationChanged(public_detail)' in tasks
    assert 'record_operational_activity(' in tasks
    assert "'report_storage_verification_completed'" in tasks
    assert "'report_storage_verification_failed'" in tasks
    assert "action_url='/reports/storage?workspace=integrity'" in tasks
    assert 'str(exc)' not in tasks.split('def _record_storage_verification_completion', 1)[1]


def test_storage_page_exposes_worker_verification_state_and_htmx_refresh() -> None:
    service = read('app/reports/storage/service.py')
    template = read('app/templates/reports/storage/index.html')
    partial = read('app/templates/reports/storage/_verification_status.html')
    routes = read('app/reports/routes.py')
    storage_routes = read('app/reports/storage/routes.py')

    assert "'verification_execution': storage_check.get_report_storage_verification_presentation(backend_name)" in service
    assert "'reports/storage/_verification_status.html'" in template
    assert 'payload.verification_execution' in template
    assert 'data-report-storage-verification-status="true"' in partial
    assert "hx-get=\"{{ url_for('reports.storage_verification_status') }}\"" in partial
    assert "every 3s" in partial
    assert 'Queued' in partial
    assert 'Verifying' in partial
    assert 'Healthy' in partial
    assert 'Failed' in partial
    assert 'Traceback' not in partial
    assert 'ReadTimeoutError' not in partial

    assert "'/storage/verification/status'" in routes
    assert "endpoint='storage_verification_status'" in routes
    assert 'def storage_verification_status()' in storage_routes


def test_web_requests_do_not_probe_s3_when_shared_worker_monitor_is_enabled() -> None:
    service = read('app/reports/storage/service.py')
    verification = read('app/reports/storage/verification.py')
    assert 'def worker_managed_storage_readiness_enabled() -> bool:' in verification
    assert 'def request_readiness_fallback(' in verification
    configured_check = service.index("configured = bool(health.get('configuration_complete', False))")
    guard = service.index('if fallback := storage_check.request_readiness_fallback(')
    probe = service.index("backend = build_report_storage_backend('s3')")
    assert configured_check < guard < probe
    assert 'return fallback' in service[guard:probe]


def test_manual_storage_verification_task_is_routed_to_storage_health_queue() -> None:
    config = read('app/config/default.py')

    assert "'app.reports.storage.tasks.verify_report_storage_task'" in config
    route = config.split("'app.reports.storage.tasks.verify_report_storage_task'", 1)[1].split('},', 1)[0]
    assert 'REPORT_STORAGE_HEALTH_CELERY_QUEUE' in route
