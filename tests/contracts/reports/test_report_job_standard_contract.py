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
