from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_terminal_status_refresh_does_not_replace_configuration_forms() -> None:
    workspace = _read('app/templates/platform_operations/jobs/configuration/_job_workspace.html')
    poller = _read('app/templates/platform_operations/jobs/configuration/_live_poller.html')
    response = _read('app/templates/platform_operations/jobs/configuration/_live_status_response.html')
    routes = _read('app/platform_operations/jobs/routes.py')

    assert 'hx-trigger="every 2s"' not in workspace
    assert 'job-configuration-live-poller' in poller
    assert '_execution_activity.html' in response
    assert '_selected_status.html' in response
    assert "@bp.get('/configuration/<path:job_key>/status')" in routes
    assert "render_template('platform_operations/jobs/configuration/_live_status_response.html'" in routes


def test_active_queries_ignore_completed_executions() -> None:
    for relative in (
        'app/kubernetes/inventory/job_adapter.py',
        'app/kubernetes/governance/tls_certificates/job_adapter.py',
        'app/kubernetes/analytics/job_adapter.py',
    ):
        content = _read(relative)
        assert 'JobExecution.completed_at.is_(None)' in content


def test_every_registered_job_uses_shared_execution_and_recent_activity_workspace() -> None:
    for relative in (
        'app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/tls_certificate_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html',
    ):
        content = _read(relative)
        assert 'platform_operations/jobs/configuration/_job_overview.html' in content
        assert 'platform_operations/jobs/configuration/_execution_activity.html' in content
        assert 'lg:grid-cols-2 lg:items-start' not in content
        assert 'xl:sticky' not in content

    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    assert 'Execution &amp; Recent Activity' in activity
    assert 'Recent Executions' in activity
    assert 'definition.recent_execution_summary' in activity
    assert 'Execution Safety:' in activity


def test_precomputed_ranges_are_compact_and_not_forced_into_seven_columns() -> None:
    analytics = _read('app/templates/platform_operations/jobs/configuration/definitions/analytics_refresh.html')
    forecast = _read('app/templates/platform_operations/jobs/configuration/definitions/forecast_refresh.html')

    assert 'Precomputed Time Ranges' in analytics
    assert 'sm:grid-cols-2 lg:grid-cols-4' in analytics
    assert 'xl:grid-cols-7' not in analytics
    assert 'Precomputed History Windows' in forecast
    assert 'sm:grid-cols-3' in forecast


def test_job_definitions_provide_job_specific_execution_history_descriptions() -> None:
    content = _read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    assert content.count('execution_summary:') >= 7
    assert content.count('recent_execution_summary:') >= 7


def test_registered_job_configuration_templates_use_canonical_platform_operations_namespace() -> None:
    catalog = _read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    template_names = [
        line.split(':', 1)[1].strip()
        for line in catalog.splitlines()
        if line.strip().startswith('configuration_template:')
    ]
    assert template_names
    for template_name in template_names:
        assert template_name.startswith('platform_operations/jobs/configuration/definitions/')
        assert (ROOT / 'app/templates' / template_name).is_file(), template_name

def test_job_configuration_one_line_helpers_preserve_source_evidence() -> None:
    overview = _read('app/templates/platform_operations/jobs/configuration/_job_overview.html')
    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    inventory = _read('app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html')
    tenant = _read('app/templates/platform_operations/jobs/configuration/definitions/tenant_sync.html')
    storage = _read(
        'app/templates/platform_operations/jobs/configuration/definitions/object_storage_inventory_sync.html'
    )

    assert 'sm:grid-cols-2 2xl:grid-cols-4' in overview
    assert "label == 'Next Automatic Run'" in overview
    assert 'whitespace-nowrap text-xs tabular-nums' in overview
    assert 'title="{{ value }}"' in overview
    assert 'title="{{ helper }}"' in overview
    assert 'xl:truncate' in overview
    assert 'lg:truncate' in activity
    assert 'same execution and audit trail' in activity
    assert 'whitespace-nowrap' in activity
    for source in (inventory, tenant, storage):
        assert 'block truncate text-xs leading-5' in source
        assert 'title=' in source
    assert 'Guarded Recovery Boundary' in storage
    assert "variant='guide'" in storage
    assert 'Mismatch stops recovery safely; no records are deleted.' in storage
    assert 'recovery fails closed without deleting records.' in storage
    assert 'name="confirmation_phrase"' in storage
    assert 'name="confirm_empty_system_id"' in storage
