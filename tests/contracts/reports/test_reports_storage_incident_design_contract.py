from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_reports_recovery_view_uses_one_unified_operational_incident_panel() -> None:
    source = read('app/templates/reports/_unavailable.html')
    web = read('app/reports/web.py')

    assert 'data-reports-recovery-panel="unified"' in source
    assert 'Reporting Dependency Unavailable' in source
    assert 'Operational Impact' in source
    assert 'Recommended Checks' in source
    assert 'Open Storage' in source
    assert 'Retry Storage Check' in source
    assert 'technical exception in server logs' in source
    assert 'Raw Error Hidden' in source
    assert 'What Happened' not in source
    assert 'xl:grid-cols-[minmax(0,1fr)_340px]' not in source
    assert "'storage_verify_url': url_for('reports.storage', verify=1)" in web


def test_reports_overview_surfaces_s3_disconnect_as_compact_operational_incident() -> None:
    source = read('app/templates/reports/overview/partials/_reporting_operations.html')

    assert 'data-report-storage-incident="overview"' in source
    assert "payload.storage_context.backend == 's3'" in source
    assert "payload.storage_context.status != 'selected'" in source
    assert 'S3 Report Storage Disconnected' in source
    assert 'Report records remain available' in source
    assert 'Open Storage' in source
    assert 'Retry Connection' in source
