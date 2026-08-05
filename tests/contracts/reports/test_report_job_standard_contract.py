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
