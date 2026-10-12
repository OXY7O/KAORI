from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_hot_jobs_are_fetched_once_per_visible_audit_page() -> None:
    source = read('app/access/activity_audit/administrative_sources.py')
    assert 'events, pagination = paginate_query(query, page=page, per_page=normalized_per_page)' in source
    assert 'for event in events' in source
    assert "event.target_type == 'job_execution' and event.target_id" in source
    assert 'JobExecution.query.filter(JobExecution.public_id.in_(job_ids)).all()' in source
    assert 'if can_view_jobs and job_ids' in source
    assert 'hot_jobs.get(str(event.target_id))' in source
    assert 'JobExecution.query.filter_by(public_id=event.target_id).first()' not in source


def test_archive_browse_is_permissioned_not_a_job_archive_match() -> None:
    source = read('app/access/activity_audit/administrative_sources.py')
    view = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    assert 'can_browse_job_archives: bool = False' in source
    assert "can_view_jobs and event.target_type == 'job_execution' and event.target_id" in source
    assert "job_url = url_for('jobs.executions', execution_tab='registry', search=job.public_id)" in source
    assert 'elif can_browse_job_archives:' in source
    assert "'platform_operations.data_lifecycle.index'," in source
    assert "archive_domain='job_execution'" in source
    assert "'archive_history_url': archive_history_url" in source
    for token in ('{% if row.job_url %}', '{% elif row.archive_history_url %}', '{% elif row.job_unavailable %}',
                  'Open Job', 'Browse Job Archives', 'Archive bundles only; job match not verified.',
                  'Job unavailable', 'Source-owned'):
        assert token in view
    assert 'View Archived Job' not in view


def test_all_admin_entrypoints_require_lifecycle_permission() -> None:
    routes = read('app/access/activity_audit/routes.py')
    assert routes.count('can_browse_job_archives=') == 3
    assert routes.count("current_user.has_permission('platform_operations.view_data_lifecycle')") == 2
    assert routes.count('build_administrative_evidence_context(') == 3
    assert "@permission_required('activity_audit.view')" in routes
    lifecycle = read('app/platform_operations/data_lifecycle/routes.py')
    assert "@permission_required('platform_operations.view_data_lifecycle')" in lifecycle


def test_separate_audit_sources_and_archive_reader_boundary() -> None:
    source = read('app/access/activity_audit/administrative_sources.py')
    view = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    assert 'AuditEvent.query.filter(' in source
    assert "'automatic-jobs'" in source and "'tenant-sync'" in source
    assert 'JobExecution.query' in source and 'ArchiveArtifact.query' not in source
    assert 'archive_search=' not in source
    assert 'data-activity-evidence-source="administrative-audit-events"' in view
    assert 'hx-post=' not in view
