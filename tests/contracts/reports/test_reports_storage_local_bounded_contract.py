from pathlib import Path


def test_storage_page_selects_lightweight_local_health():
    text = (Path(__file__).resolve().parents[3] / 'app/reports/storage/service.py').read_text()
    payload = text[text.index('def get_report_storage_payload(') : text.index('def verify_active_report_storage(')]
    assert 'build_local_storage_health(include_artifact_inventory=False)' in payload
    assert "'local': build_local_storage_health()" not in payload


def test_storage_ui_does_not_present_db_references_as_filesystem_census():
    text = (Path(__file__).resolve().parents[3] / 'app/templates/reports/storage/index.html').read_text()
    assert 'payload.artifact_summary.local_reports' in text
    assert 'payload.local.reports_file_count' not in text
