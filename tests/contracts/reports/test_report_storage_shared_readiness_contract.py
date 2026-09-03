from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_report_storage_readiness_is_shared_through_redis_with_freshness_metadata() -> None:
    state = read('app/reports/storage/state.py')
    service = read('app/reports/storage/service.py')

    assert "READINESS_KEY_PREFIX = 'kaori:reports:storage-readiness:'" in state
    assert "current_app.config.get('REDIS_URL')" in state
    assert "'checked_at'" in state
    assert "'source'" in state
    assert "'config_fingerprint'" in state
    assert "'stale_after_seconds'" in state
    assert "'age_seconds'" in state
    assert "'stale'" in state
    assert 'get_shared_report_storage_status' in service
    assert 'publish_shared_report_storage_status' in service

    shared_pos = service.index('shared_status = get_shared_report_storage_status')
    process_pos = service.index('process_cached = _get_process_cached_storage_status')
    probe_pos = service.index("if normalized_backend == 'local':")
    assert shared_pos < process_pos < probe_pos


def test_storage_readiness_defaults_are_documented_for_local_and_production_envs() -> None:
    for path in ('.env.example', 'deploy/env/app.env.example'):
        source = read(path)
        assert 'REPORT_STORAGE_HEALTH_MONITOR_ENABLED=true' in source
        assert 'REPORT_STORAGE_HEALTH_INTERVAL_MINUTES=1' in source
        assert 'REPORT_STORAGE_HEALTH_STALE_SECONDS=120' in source
        assert 'REPORT_STORAGE_HEALTH_STATE_TTL_SECONDS=600' in source
        assert 'REPORT_STORAGE_HEALTH_CELERY_QUEUE=maintenance' in source


def test_periodic_storage_probe_is_lightweight_and_routed_to_maintenance() -> None:
    config = read('app/config/default.py')
    tasks = read('app/reports/storage/tasks.py')
    storage = read('app/reports/storage/service.py')

    assert "schedule['report-storage-readiness']" in config
    assert 'REPORT_STORAGE_HEALTH_INTERVAL_MINUTES' in config
    assert 'REPORT_STORAGE_HEALTH_CELERY_QUEUE' in config
    assert "'app.reports.storage.tasks'" in config
    assert "'app.reports.storage.tasks.refresh_report_storage_readiness_task'" in config
    assert "source='periodic'" in tasks
    assert 'refresh_report_storage_readiness' in tasks

    refresh_start = storage.index('def refresh_report_storage_readiness(')
    refresh_end = storage.index('\ndef mark_report_storage_backend_unavailable(', refresh_start)
    refresh_body = storage[refresh_start:refresh_end]
    assert 'force=True' in refresh_body
    assert 'save_file(' not in refresh_body
    assert '.exists(' not in refresh_body
    assert '.delete(' not in refresh_body

    verify_start = storage.index('def verify_active_report_storage(')
    verify_body = storage[verify_start:]
    assert 'backend.save_file(' in verify_body
    assert 'backend.exists(' in verify_body
    assert 'backend.delete(' in verify_body
    assert "source='manual_verification'" in verify_body


def test_operation_failures_publish_immediate_degraded_readiness() -> None:
    service = read('app/reports/storage/service.py')

    assert 'def mark_report_storage_backend_unavailable(' in service
    assert "source='artifact_write_failure'" in service
    assert "source='artifact_read_failure'" in service
    assert "'manual_verification_failure'" in service
    assert "'write_verification_required': write_verification_required" in service
    assert "'state': 'unavailable'" in service
    assert "'status': 'Disconnected'" in service
    assert 'publish_shared_report_storage_status' in service


def test_connectivity_recovery_does_not_clear_a_previous_write_failure() -> None:
    service = read('app/reports/storage/service.py')

    assert 'previous_shared_status' in service
    assert "previous_shared_status.get('write_verification_required', False)" in service
    assert "source != 'manual_verification'" in service
    assert "'state': 'degraded'" in service
    assert "'status': 'Verification Required'" in service
    assert "'write_available': False" in service
    assert "'write_verification_required': True" in service
    assert 'New report generation stays paused until Test Storage succeeds.' in service


def test_overview_uses_degraded_mode_instead_of_blocking_the_workspace() -> None:
    overview = read('app/templates/reports/overview/index.html')
    posture = read('app/templates/reports/overview/partials/_reporting_operational_posture.html')
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')
    service = read('app/reports/overview/service.py')

    assert 'payload.storage_context.degraded' in overview
    assert 'Open Storage' in overview
    assert 'Generated Reports' in estate
    assert '_reporting_operational_posture.html' in overview
    assert '_reporting_estate_capability.html' in overview
    assert "'degraded': not is_ready" in service
    assert 'format_storage_check_age' in service
    assert 'monitor_interval_minutes' in service

    assert 'data-report-storage-incident="overview"' in posture
    assert 'S3 Artifact Storage Disconnected' in posture
    assert 'New artifact generation and S3-backed access stay paused' in posture
    assert 'automatic check every' in posture


def test_generate_remains_visible_but_is_guarded_before_report_creation() -> None:
    service = read('app/reports/generate/service.py')
    template = read('app/templates/reports/generate/index.html')

    assert "'generation_allowed': bool(storage_context.get('ready', False))" in service
    assert 'storage_status = get_report_storage_backend_status()' in service
    assert "if not bool(storage_status.get('write_available', False))" in service
    assert 'Artifact storage is unavailable.' in service

    gate_pos = service.index("if not bool(storage_status.get('write_available', False))")
    report_create_pos = service.index('report = Report()', gate_pos)
    assert gate_pos < report_create_pos

    assert 'payload.generation_allowed' in template
    assert 'storageGenerationReady' in template
    assert '!storageGenerationReady' in template


def test_schedule_management_remains_visible_but_execution_is_guarded() -> None:
    service = read('app/reports/schedules/service.py')
    adapter = read('app/reports/schedules/job_adapter.py')
    template = read('app/templates/reports/schedules/index.html')

    assert "'run_actions_enabled': bool(storage_context.get('ready', False))" in service
    assert 'get_report_storage_backend_status(backend_name)' in service
    assert "if not bool(storage_status.get('write_available', False))" in service

    gate_pos = service.index("if not bool(storage_status.get('write_available', False))")
    create_pos = service.index('report = _create_report_from_schedule(schedule)', gate_pos)
    assert gate_pos < create_pos

    assert 'get_report_storage_backend_status()' in adapter
    assert 'Run Now is paused until storage recovers.' in adapter
    assert 'payload.run_actions_enabled' in template


def test_generated_report_registry_degrades_per_artifact_instead_of_global_block() -> None:
    service = read('app/reports/generated/service.py')
    index = read('app/templates/reports/generated/index.html')
    detail = read('app/templates/reports/generated/detail.html')

    assert 'get_report_storage_backend_status()' in service
    assert 'probe_report_artifact' in service
    assert "'storage_notice': storage_notice" in service
    assert "'can_download_artifact': can_download_artifact" in service
    assert 'payload.storage_notice' in index
    assert 'report.can_download_artifact' in index
    assert 'payload.report.can_download_artifact' in detail


def test_storage_page_exposes_monitor_state_without_exposing_credentials() -> None:
    storage = read('app/templates/reports/storage/index.html')
    service = read('app/reports/storage/service.py')

    assert 'data-report-storage-readiness-monitor="true"' in storage
    assert 'Every {{ payload.readiness_monitor.interval_minutes }} min' in storage
    assert 'payload.readiness_monitor.interval_minutes' in storage
    assert 'payload.readiness_monitor.checked_label' in storage
    assert "'shared_state': bool(current_app.config.get('REDIS_URL'))" in service
    assert "'source': str(backend_status.get('source') or 'direct')" in service
