from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app' / 'templates'


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_job_configuration_statuses_use_dot_indicator_labels() -> None:
    table_label = _read('app/templates/components/table_label.html')
    assert 'macro status_indicator_label' in table_label
    indicator = table_label.split('macro status_indicator_label', 1)[1].split('endmacro', 1)[0]
    assert 'rounded-full' in indicator
    assert 'data-lucide' not in indicator

    for relative in (
        'app/templates/platform_operations/jobs/configuration/_workspace.html',
        'app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html',
        'app/templates/platform_operations/jobs/configuration/definitions/tls_certificate_sync.html',
    ):
        content = _read(relative)
        assert 'table_label.status_indicator_label' in content


def test_active_progress_is_determinate_without_restarting_animation() -> None:
    progress = _read('app/templates/components/progress_bar.html')
    assert 'macro determinate' in progress
    assert '<progress' in progress
    assert 'transition-all' not in _read('app/templates/components/navigation/_quick_sync_status.html')

    assert 'progress_bar.job_progress' in _read(
        'app/templates/platform_operations/jobs/configuration/_execution_activity.html'
    )
    quick_sync = _read('app/templates/components/navigation/_quick_sync_status.html')
    shared_progress = _read('app/templates/components/operational_progress_toast.html')
    assert 'components/operational_progress_toast.html' in quick_sync
    assert 'progress_toast.render' in quick_sync
    assert 'progress_bar.notification_progress' in shared_progress
    assert 'progress_bar.notification_indeterminate' in shared_progress
    assert 'progress_bar.determinate' not in shared_progress

    for relative in (
        'app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html',
        'app/templates/platform_operations/jobs/configuration/definitions/tls_certificate_sync.html',
    ):
        assert 'platform_operations/jobs/configuration/_execution_activity.html' in _read(relative)


def test_job_catalog_status_refreshes_out_of_band() -> None:
    workspace = _read('app/templates/platform_operations/jobs/configuration/_workspace.html')
    job_workspace = _read('app/templates/platform_operations/jobs/configuration/_job_workspace.html')
    poller = _read('app/templates/platform_operations/jobs/configuration/_live_poller.html')
    response = _read('app/templates/platform_operations/jobs/configuration/_live_status_response.html')
    oob = _read('app/templates/platform_operations/jobs/configuration/_catalog_status_oob.html')
    routes = _read('app/platform_operations/jobs/routes.py')

    assert 'job-catalog-status-' in workspace
    assert 'job-catalog-activity-' in workspace
    assert '_live_poller.html' in job_workspace
    assert '_catalog_status_oob.html' in response
    assert 'hx-swap-oob="outerHTML"' in oob
    assert 'configuration_status' in routes
    assert "Cache-Control'] = 'no-store, max-age=0'" in routes
    assert 'hx-sync="this:replace"' in poller
    assert '{% if selected_job.active_job %}' in poller
    assert 'hx-trigger="every 10s"' in poller
    assert 'every 30s' not in poller
    assert 'build_job_configuration_live_context' in routes


def test_registered_job_descriptions_are_compact() -> None:
    content = _read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    for phrase in (
        'Refresh Kubernetes inventory across eligible clusters.',
        'Refresh shared Kubernetes analytics snapshots.',
        'Dispatch due report schedules through the Reports worker.',
        'Generate persistent capacity forecasts',
        'Refresh TLS Secret inventory',
    ):
        assert phrase in content
    assert max(len(line) for line in content.splitlines()) < 130
