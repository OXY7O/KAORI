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
        'app/templates/jobs/configuration/_workspace.html',
        'app/templates/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/jobs/configuration/definitions/_materialization_job.html',
        'app/templates/jobs/configuration/definitions/tls_certificate_sync.html',
    ):
        content = _read(relative)
        assert 'table_label.status_indicator_label' in content


def test_active_progress_is_determinate_without_restarting_animation() -> None:
    progress = _read('app/templates/components/progress_bar.html')
    assert 'macro determinate' in progress
    assert '<progress' in progress
    assert 'transition-all' not in _read(
        'app/templates/components/navigation/_quick_sync_status.html'
    )

    for relative in (
        'app/templates/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/jobs/configuration/definitions/_materialization_job.html',
        'app/templates/jobs/configuration/definitions/tls_certificate_sync.html',
        'app/templates/components/navigation/_quick_sync_status.html',
    ):
        assert 'progress_bar.determinate' in _read(relative)


def test_job_catalog_status_refreshes_out_of_band() -> None:
    workspace = _read('app/templates/jobs/configuration/_workspace.html')
    job_workspace = _read('app/templates/jobs/configuration/_job_workspace.html')
    oob = _read('app/templates/jobs/configuration/_catalog_status_oob.html')
    routes = _read('app/jobs/routes.py')

    assert 'job-catalog-status-' in workspace
    assert 'job-catalog-activity-' in workspace
    assert '_catalog_status_oob.html' in job_workspace
    assert 'hx-swap-oob="outerHTML"' in oob
    assert "Cache-Control'] = 'no-store, max-age=0'" in routes
    assert 'hx-sync="this:replace"' in job_workspace


def test_registered_job_descriptions_are_compact() -> None:
    expected = {
        'app/jobs/definitions/inventory_sync.py': 'Refresh cluster inventory snapshots',
        'app/jobs/definitions/analytics_refresh.py': 'Refresh shared Kubernetes analytics snapshots',
        'app/jobs/definitions/forecast_refresh.py': 'Generate persistent capacity forecasts',
        'app/jobs/definitions/tls_certificate_sync.py': 'Refresh TLS Secret inventory',
    }
    for relative, phrase in expected.items():
        content = _read(relative)
        assert phrase in content
        assert max(len(line) for line in content.splitlines()) < 130
