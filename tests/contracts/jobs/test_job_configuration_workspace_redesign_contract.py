from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_terminal_status_refresh_does_not_replace_configuration_forms() -> None:
    workspace = _read('app/templates/jobs/configuration/_job_workspace.html')
    poller = _read('app/templates/jobs/configuration/_live_poller.html')
    response = _read('app/templates/jobs/configuration/_live_status_response.html')
    routes = _read('app/jobs/routes.py')

    assert 'hx-trigger="every 2s"' not in workspace
    assert 'job-configuration-live-poller' in poller
    assert '_execution_activity.html' in response
    assert '_selected_status.html' in response
    assert "@bp.get('/configuration/<path:job_key>/status')" in routes
    assert "render_template('jobs/configuration/_live_status_response.html'" in routes


def test_active_queries_ignore_completed_executions() -> None:
    for relative in (
        'app/inventory/kubernetes/job_adapter.py',
        'app/governance/tls_certificates/job_adapter.py',
        'app/analytics/kubernetes/job_adapter.py',
    ):
        content = _read(relative)
        assert 'JobExecution.completed_at.is_(None)' in content


def test_every_registered_job_uses_shared_execution_and_recent_activity_workspace() -> None:
    for relative in (
        'app/templates/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/jobs/configuration/definitions/tls_certificate_sync.html',
        'app/templates/jobs/configuration/definitions/_materialization_job.html',
    ):
        content = _read(relative)
        assert 'jobs/configuration/_job_overview.html' in content
        assert 'jobs/configuration/_execution_activity.html' in content
        assert 'lg:grid-cols-2 lg:items-start' not in content
        assert 'xl:sticky' not in content

    activity = _read('app/templates/jobs/configuration/_execution_activity.html')
    assert 'Execution &amp; Recent Activity' in activity
    assert 'Recent Executions' in activity
    assert 'definition.recent_execution_summary' in activity
    assert 'Execution Safety:' in activity


def test_precomputed_ranges_are_compact_and_not_forced_into_seven_columns() -> None:
    analytics = _read('app/templates/jobs/configuration/definitions/analytics_refresh.html')
    forecast = _read('app/templates/jobs/configuration/definitions/forecast_refresh.html')

    assert 'Precomputed Time Ranges' in analytics
    assert 'sm:grid-cols-2 lg:grid-cols-4' in analytics
    assert 'xl:grid-cols-7' not in analytics
    assert 'Precomputed History Windows' in forecast
    assert 'sm:grid-cols-3' in forecast


def test_job_definitions_provide_job_specific_execution_history_descriptions() -> None:
    content = _read('app/definitions/catalogs/jobs/registered_jobs.yaml')
    assert content.count('execution_summary:') >= 7
    assert content.count('recent_execution_summary:') >= 7
