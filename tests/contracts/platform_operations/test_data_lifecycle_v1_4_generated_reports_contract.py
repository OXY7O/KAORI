from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_generated_reports_are_a_registered_lifecycle_domain() -> None:
    registry = read('app/retention/domains/__init__.py')
    adapter = read('app/retention/domains/generated_report.py')

    assert 'from app.retention.domains.generated_report import GeneratedReportArchiveDomain' in registry
    assert "'generated_report': GeneratedReportArchiveDomain" in registry
    assert "name = 'generated_report'" in adapter
    assert "source_model = 'reports'" in adapter
    assert "_TERMINAL_REPORT_STATUSES = ('ready', 'failed', 'archived')" in adapter


def test_generated_report_cleanup_is_age_based_and_protects_active_generation() -> None:
    adapter = read('app/retention/domains/generated_report.py')

    assert "Report.status == 'ready'" in adapter
    assert "Report.status == 'archived'" in adapter
    assert "Report.status == 'failed'" in adapter
    assert "_ACTIVE_JOB_STATUSES = ('queued', 'running', 'retrying', 'cancel_requested')" in adapter
    assert 'Report.job_execution_id.notin_(active_jobs)' in adapter
    assert 'Report.file_path.is_not(None)' in adapter
    assert "'failed_retention_days'" in adapter
    assert "'archived_retention_days'" in adapter
    assert 'if report.status in _ARTIFACT_REPORT_STATUSES and report.file_path:' in adapter


def test_generated_report_archive_copies_and_verifies_binary_evidence_before_cleanup() -> None:
    adapter = read('app/retention/domains/generated_report.py')
    service = read('app/retention/service.py')

    assert 'def iter_supplements(' in adapter
    assert 'ArchiveSupplement(' in adapter
    assert 'build_report_download_path(stored_path)' in adapter
    assert 'Report.id > last_id' in adapter
    assert '.limit(policy.batch_size)' in adapter
    assert "relative_path=f'report-{report.id}/{filename}'" in adapter
    assert 'def _store_supplemental_artifacts(' in service
    assert "'supplemental_artifacts': supplemental_artifacts" in service
    assert "object_key = f'{object_prefix}/{artifact.id}/artifacts/{relative_path}'" in service
    assert '_verify_supplemental_artifacts(backend=backend, artifact=artifact)' in service
    assert "'supplemental_artifacts': _supplemental_artifacts(artifact)" in service
    assert 'for supplemental in _supplemental_artifacts(artifact):' in service


def test_generated_report_policy_is_bounded_and_scheduled_separately() -> None:
    config = read('app/config/default.py')
    tasks = read('app/retention/tasks.py')
    policy = read('app/retention/policy_service.py')
    lifecycle_service = read('app/platform_operations/data_lifecycle/service.py')
    migration = read('migrations/versions/20260816_generated_report_data_lifecycle.py')

    for key in (
        'GENERATED_REPORT_RETENTION_ENABLED',
        'GENERATED_REPORT_RETENTION_DAYS',
        'GENERATED_REPORT_ARCHIVE_RETENTION_DAYS',
        'GENERATED_REPORT_RETENTION_BATCH_SIZE',
        'GENERATED_REPORT_FAILED_RETENTION_DAYS',
        'GENERATED_REPORT_ARCHIVED_RETENTION_DAYS',
        'GENERATED_REPORT_RETENTION_SCHEDULE_HOUR',
        'GENERATED_REPORT_RETENTION_SCHEDULE_MINUTE',
    ):
        assert key in config

    assert "'generated_report'" in tasks
    assert "if domain == 'generated_report':" in policy
    assert "'ix_reports_retention_boundary'" in migration
    assert "revision = '20260816_report_lifecycle'" in migration
    assert '20260816_generated_report_lifecycle' not in migration
    assert "domain='generated_report'" in migration
    assert 'batch_size=250' in migration
    assert 'enabled=False' in migration
    assert 'REPORT_DESTRUCTIVE_CLEANUP_ENABLED' not in config
    assert 'REPORT_CLEANUP_MODE' not in config
    assert 'REPORT_CLEANUP_SCOPE' not in config
    assert 'schedule_enabled=False' in migration
    assert "GENERATED_REPORT_RETENTION_ENABLED = _env_bool('GENERATED_REPORT_RETENTION_ENABLED', False)" in config
    assert 'return replace(policy, batch_size=max(100, min(policy.batch_size, 2500)))' in read(
        'app/retention/domains/generated_report.py'
    )
    assert 'batch_size = max(100, min(batch_size, 2500))' in lifecycle_service


def test_data_lifecycle_ui_explains_generated_report_evidence_and_status_windows() -> None:
    presentation = read('app/retention/presentation.py')
    generated_presentation = read('app/retention/generated_report_presentation.py')
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')

    assert "'generated_report': generated_report_ui.GENERATED_REPORT_LABEL" in presentation
    assert "GENERATED_REPORT_LABEL = 'Generated Reports'" in generated_presentation
    assert "'label': 'Generated Registry'" in generated_presentation
    assert "'label': 'Artifact Evidence'" in generated_presentation
    assert "selected.name == 'generated_report'" in workspace
    assert 'Generated Report Evidence Protection' in workspace
    assert 'failed_retention_days' in workspace
    assert 'archived_retention_days' in workspace
    assert 'max="{{ 2500 if selected.name == \'generated_report\' else 25000 }}"' in workspace
    assert 'verify SHA-256 before the source artifact or database row can be cleaned' in workspace
    assert 'generated_report_ui.GENERATED_REPORT_COVERAGE_NOTE' in presentation


def test_generated_registry_does_not_advertise_page_size_options_in_posture_banner() -> None:
    generated = read('app/templates/reports/generated/index.html')

    assert 'Rows 5 / 10 / 25 / 50' not in generated
    assert 'Storage-Aware Downloads' in generated
    assert "domain='generated_report'" in generated
    assert 'Data Lifecycle' in generated


def test_report_storage_reads_generated_lifecycle_policy_as_the_canonical_retention_source() -> None:
    health = read('app/reports/storage/health.py')
    service = read('app/reports/storage/service.py')
    storage_template = read('app/templates/reports/storage/index.html')

    assert "DataLifecyclePolicy.query.filter_by(domain='generated_report').first()" in health
    assert "'status': 'Lifecycle Managed' if lifecycle_enabled else 'Lifecycle Paused'" in health
    assert (
        'Platform Operations → Data Lifecycle is the authoritative control plane for Generated Reports retention'
        in health
    )
    assert 'Generated Report Lifecycle Policy' in storage_template
    assert 'Open Data Lifecycle' in storage_template
    assert 'Lifecycle Actions Live in Data Lifecycle' in storage_template
    assert 'Storage Candidate Preview' not in storage_template
    assert 'build_report_cleanup_dry_run' not in service
    assert 'cleanup_dry_run' not in service


def test_generated_report_archives_surface_binary_evidence_in_archive_history() -> None:
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')
    presentation = read('app/retention/presentation.py')

    assert "'supplemental_count': len(metadata.get('supplemental_artifacts') or [])" in presentation
    assert 'retained evidence' in history
    assert "kind='manifest'" in history


def test_report_exports_stamp_the_canonical_generated_report_hot_retention_window() -> None:
    pdf_renderer = read('app/reports/export/html_pdf/renderer.py')
    csv_renderer = read('app/reports/export/csv/renderer.py')

    for renderer in (pdf_renderer, csv_renderer):
        assert 'get_generated_report_hot_retention_days' in renderer
        assert 'retention_days=get_generated_report_hot_retention_days()' in renderer
