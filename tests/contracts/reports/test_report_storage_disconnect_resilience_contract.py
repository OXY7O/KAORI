from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STORAGE_SERVICE = ROOT / 'app/reports/storage/service.py'
STORAGE_ROUTES = ROOT / 'app/reports/storage/routes.py'
STORAGE_TEMPLATE = ROOT / 'app/templates/reports/storage/index.html'
GENERATED_SERVICE = ROOT / 'app/reports/generated/service.py'
GENERATED_TEMPLATE = ROOT / 'app/templates/reports/generated/index.html'
EXPORT_SERVICE = ROOT / 'app/reports/export/service.py'
S3_STORAGE = ROOT / 'app/artifact_storage/s3.py'
CONFIG = ROOT / 'app/config/default.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_s3_disconnect_is_a_sanitized_cached_state() -> None:
    source = read(STORAGE_SERVICE)

    assert 'def get_report_storage_backend_status(' in source
    assert "'status': 'Disconnected'" in source
    assert "'state': 'unavailable'" in source
    assert "'read_available': False" in source
    assert "'write_available': False" in source
    assert '_PROCESS_STORAGE_STATUS_CACHE' in source
    assert 'REPORT_STORAGE_STATUS_CACHE_SECONDS' in source
    assert 'S3-compatible report storage is configured but unreachable.' in source


def test_storage_page_stays_available_and_shows_reconnect_guidance() -> None:
    route_source = read(STORAGE_ROUTES)
    template = read(STORAGE_TEMPLATE)

    assert 'payload = get_report_storage_payload(workspace=workspace)' in route_source
    assert "if payload['integrity_actions_enabled']" in route_source
    assert 'report-storage-connectivity-title' in template
    assert 'Storage Operations' in template
    assert 'data-report-storage-readiness-monitor="true"' in template
    assert 'Verify Connection' in template
    assert "url_for('reports.verify_storage')" in template
    assert 'method="post"' in template
    assert 'Integrity Check Paused' in template
    assert 'Lifecycle Actions Live in Data Lifecycle' in template
    assert 'Traceback' not in template
    assert 'EndpointConnectionError' not in template


def test_generated_pages_use_safe_probe_and_pause_storage_actions() -> None:
    service = read(GENERATED_SERVICE)
    template = read(GENERATED_TEMPLATE)

    assert 'get_report_storage_backend_status' in service
    assert 'return probe_report_artifact(file_path)' in service
    serialize_report = service.split('def _serialize_report(', 1)[1].split('def _summarize_report_file_reference(', 1)[
        0
    ]
    assert 'can_generate_artifact = report.status' in serialize_report
    assert "active_backend_status.get('write_available', False)" in serialize_report
    assert "if not bool(backend_status.get('available', False)):" in service
    assert 'storage-dependent operations follow ' in service
    assert 'the active backend readiness state.' in service
    assert 'download ' in service
    assert 'actions stay paused until connectivity returns.' in service
    assert 'data-generated-storage-degraded="true"' in template
    assert 'payload.backend_status.title' in template


def test_generation_fails_before_rendering_when_active_storage_is_down() -> None:
    source = read(EXPORT_SERVICE)

    status_index = source.index('backend_status = get_report_storage_backend_status()')
    renderer_index = source.index('artifact_format.renderer(report, staging_path)')

    assert status_index < renderer_index
    assert "if not bool(backend_status.get('write_available', False)):" in source
    assert 'The report request remains unchanged' in source


def test_s3_client_has_bounded_timeout_and_retry_configuration() -> None:
    storage = read(S3_STORAGE)
    config = read(CONFIG)

    assert "'connect_timeout': max(int(connect_timeout_seconds), 1)" in storage
    assert "'read_timeout': max(int(read_timeout_seconds), 1)" in storage
    assert "'total_max_attempts': max(int(max_attempts), 1)" in storage
    assert 'REPORT_S3_CONNECT_TIMEOUT_SECONDS' in config
    assert 'REPORT_S3_READ_TIMEOUT_SECONDS' in config
    assert 'REPORT_S3_MAX_ATTEMPTS' in config
    assert 'REPORT_STORAGE_STATUS_CACHE_SECONDS' in config


def test_integrity_results_do_not_expose_raw_storage_exception_text() -> None:
    source = read(STORAGE_SERVICE)

    assert "'error': 'Storage backend was unavailable during this integrity check.'" in source
    assert 'cleanup preview' not in source.lower()
    assert "'error': str(" not in source
    assert 'error=str(' not in source
