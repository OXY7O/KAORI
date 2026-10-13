from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_web_integrity_endpoint_dispatches_worker_job_instead_of_probing():
    routes = (ROOT / 'app/reports/storage/routes.py').read_text()
    jobs = (ROOT / 'app/reports/storage/jobs.py').read_text()
    tasks = (ROOT / 'app/reports/storage/tasks.py').read_text()
    assert 'scan_report_storage_integrity()' not in routes
    assert 'enqueue_report_storage_integrity_scan' in routes
    assert "operation='scan_integrity'" in jobs
    assert 'require_registered_worker=True' in jobs
    assert 'scan_report_storage_integrity(max_items=500)' in tasks
    assert 'result_summary=result' in tasks


def test_ui_reads_committed_scan_result_and_polls_active_job():
    service = (ROOT / 'app/reports/storage/service.py').read_text()
    verify = (ROOT / 'app/reports/storage/verification.py').read_text()
    page = (ROOT / 'app/templates/reports/storage/index.html').read_text()
    assert 'get_report_storage_integrity_scan_presentation' in verify
    assert 'dict(completed.result_summary_json)' in verify
    assert "'integrity_result': integrity_result" in service
    assert 'hx-select="[data-storage-reference-integrity]"' in page
    assert 'payload.integrity_execution.is_active' in page
