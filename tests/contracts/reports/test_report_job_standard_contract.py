from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_report_job_contract_distinguishes_time_range_and_snapshot() -> None:
    text = read('app/reports/jobs/contract.py')
    assert "execution_mode = 'time_range'" in text
    assert "execution_mode = 'committed_snapshot'" in text
    assert 'latest_committed_generation_at_or_before_cutoff' in text


def test_generate_and_schedule_use_canonical_dispatcher() -> None:
    assert 'enqueue_report_generation' in read('app/reports/generate/routes.py')
    schedule = read('app/reports/schedules/service.py')
    assert 'enqueue_report_generation' in schedule
    assert 'generate_report_artifact(report.id)' not in schedule


def test_report_worker_is_registered_and_notifies() -> None:
    config = read('app/config/default.py')
    assert 'app.reports.jobs.tasks.generate_report_job' in config
    task = read('app/reports/jobs/tasks.py')
    assert 'JobExecutionContext' in task
    assert 'report_generation_completed' in task
    assert 'report_generation_failed' in task


def test_schedule_worker_finalizes_the_exact_schedule_run() -> None:
    service = read('app/reports/jobs/service.py')
    task = read('app/reports/jobs/tasks.py')

    assert "'schedule_run_id': schedule_run_id" in service
    assert 'schedule_run_id: int | None = None' in task
    assert 'db.session.get(ReportScheduleRun, schedule_run_id)' in task
    assert 'run.report_id != report.id' in task
    assert 'order_by(ReportScheduleRun.id.desc())' not in task


def test_report_worker_hides_raw_delivery_exceptions_from_public_feedback() -> None:
    task = read('app/reports/jobs/tasks.py')

    assert '_PUBLIC_WORKER_FAILURE_MESSAGE' in task
    assert 'message=public_failure_message' in task
    assert '_notify(job, report, success=False, message=str(exc))' not in task


def test_report_dispatchers_share_the_configured_queue_contract() -> None:
    queue = read('app/reports/jobs/queue.py')
    generation = read('app/reports/jobs/service.py')
    schedule = read('app/reports/schedules/job_adapter.py')

    assert "DEFAULT_REPORTS_QUEUE = 'reports'" in queue
    assert 'current_app.config.get(' in queue
    assert "'REPORTS_CELERY_QUEUE'" in queue
    assert 'queue_name=get_reports_queue_name()' in generation
    assert 'queue_name=get_reports_queue_name()' in schedule
    assert "QUEUE_NAME = 'reports'" not in generation
    assert "QUEUE_NAME = 'reports'" not in schedule


def test_report_workspaces_surface_actual_worker_queue_readiness() -> None:
    schedules = read('app/reports/schedules/service.py')
    schedule_template = read('app/templates/reports/schedules/index.html')
    overview = read('app/reports/overview/service.py')
    generate = read('app/reports/generate/service.py')
    notifications = read('app/notifications/queries.py')
    activity_item = read('app/templates/notifications/components/_activity_center_items.html')

    assert 'get_queue_readiness(get_reports_queue_name())' in schedules
    assert 'payload.worker_context.show_warning' in schedule_template
    assert 'get_queue_readiness(get_reports_queue_name())' in overview
    assert 'get_queue_readiness(get_reports_queue_name())' in generate
    assert 'inspect_celery_topology()' in notifications
    assert 'job.queue_health.show_warning' in activity_item


def test_generate_report_copy_matches_automatic_worker_dispatch() -> None:
    generate = read('app/reports/generate/service.py')
    template = read('app/templates/reports/generate/index.html')
    pipeline = read('app/templates/reports/overview/partials/_pipeline_status.html')

    assert 'Create & Queue Request' in generate
    assert 'Create & Queue Report' in template
    assert 'queued automatically' in template.lower()
    assert 'generation starts separately from Generated Reports' not in template
    assert 'request-to-artifact flow' in template
    assert 'manual and scheduled requests both create a report record' in pipeline



def test_live_reports_worker_verifier_checks_queue_and_task_registration() -> None:
    verifier = read('scripts/verify_reports_worker_runtime.py')

    assert 'REPORTS_CELERY_QUEUE' in verifier
    assert 'active_queues()' in verifier
    assert 'registered()' in verifier
    assert 'app.reports.jobs.tasks.generate_report_job' in verifier
    assert 'app.reports.schedules.tasks.run_report_schedule_job' in verifier
