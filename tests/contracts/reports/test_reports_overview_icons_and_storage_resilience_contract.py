from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview' / 'partials'
OVERVIEW_SERVICE = ROOT / 'app' / 'reports' / 'overview' / 'service.py'
GENERATED_SERVICE = ROOT / 'app' / 'reports' / 'generated' / 'service.py'
STORAGE_SERVICE = ROOT / 'app' / 'reports' / 'storage' / 'service.py'
GENERATED_DETAIL = ROOT / 'app' / 'templates' / 'reports' / 'generated' / 'detail.html'
EXPORT_SERVICE = ROOT / 'app' / 'reports' / 'export' / 'service.py'


def read(path: Path) -> str:
    return path.read_text()


def test_recent_report_names_and_reporting_capability_have_visible_icons() -> None:
    recent = read(OVERVIEW / '_recent_reports.html')
    capability = read(OVERVIEW / '_coverage_pipeline_workspace.html')
    service = read(OVERVIEW_SERVICE)

    assert "'icon': str(report_type_option.get('icon', 'file-text'))" in service
    assert 'data-lucide="{{ report.icon|default(\'file-text\') }}"' in recent
    assert recent.index('report.icon') < recent.index('{{ report.name }}')

    assert 'data-lucide="workflow"' in capability
    assert 'Reporting Capability' in capability
    assert 'border-kaori-primary/20' in capability


def test_report_detail_storage_probe_is_failure_tolerant() -> None:
    generated_service = read(GENERATED_SERVICE)
    storage_service = read(STORAGE_SERVICE)

    assert 'def _probe_report_file(' in generated_service
    assert 'return probe_report_artifact(file_path)' in generated_service
    assert 'def probe_report_artifact(' in storage_service
    assert 'parse_report_storage_uri(' in storage_service
    assert 'except Exception:' in storage_service
    assert "'reachable': False" in storage_service
    assert "'state': 'unavailable'" in storage_service
    assert 'current_app.logger.warning(' in storage_service
    assert 'def get_report_artifact_access_notice(' in generated_service
    assert 'Artifact Storage Is Temporarily Unavailable' in generated_service
    assert 'Download is paused to avoid a failed request.' in generated_service


def test_report_detail_renders_friendly_storage_notice_instead_of_raw_error() -> None:
    detail = read(GENERATED_DETAIL)

    assert '{% if payload.artifact_access_notice %}' in detail
    assert 'artifact-storage-unavailable-title' in detail
    assert 'payload.artifact_access_notice.action_label' in detail
    assert 'payload.artifact_access_notice.description' in detail
    assert 'payload.report.storage_reachable' not in detail
    assert 'Traceback' not in detail
    assert 'ClientError' not in detail


def test_report_download_storage_failure_returns_friendly_feedback() -> None:
    service = read(EXPORT_SERVICE)

    assert 'Unable to access report artifact for download.' in service
    assert 'Report storage is temporarily unavailable. Restore storage connectivity and try again.' in service
    assert 'except Exception:' in service
