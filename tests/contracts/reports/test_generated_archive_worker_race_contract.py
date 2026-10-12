from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_archive_uses_locked_report_and_canonical_active_job_evidence() -> None:
    source = (ROOT / 'app/reports/generated/service.py').read_text()
    assert 'ACTIVE_GENERATION_JOB_STATUSES' in source
    assert "JobExecution.resource_group.in_(groups)" in source
    assert "JobExecution.status.in_(ACTIVE_GENERATION_JOB_STATUSES)" in source
    assert 'active_generation_ids = _get_active_report_generation_ids(report_items)' in source
    assert 'report.id in _get_active_report_generation_ids([report])' in source
    assert source.count('.with_for_update()') >= 2
    assert "'can_archive_report': report_item['can_archive_report']" in source
    assert 'if ineligible or active_ids:' in source
    assert 'No reports archived:' in source


def test_worker_checks_archive_after_storage_preflight_under_lock() -> None:
    source = (ROOT / 'app/reports/export/service.py').read_text()
    assert '.with_for_update()' in source
    assert "report is None or report.status == 'archived'" in source
    assert source.index("report is None or report.status == 'archived'") < source.index("report.status = 'generating'")
    assert "failed_report is not None and failed_report.status != 'archived'" in source
