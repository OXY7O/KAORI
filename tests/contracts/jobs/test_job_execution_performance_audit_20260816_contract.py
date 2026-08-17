from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_parent_jobs_workspaces_are_server_owned_and_not_built_together() -> None:
    page = read('app/templates/jobs/index.html')
    routes = read('app/jobs/routes.py')

    assert 'framed_workspace_tabs.render_navigation' in page
    assert "{% if active_jobs_section == 'configuration' %}" in page
    assert 'x-show="activeTab ===' not in page
    assert "if active_section == 'configuration':" in routes
    assert 'build_job_configuration_summary_context' in routes
    assert "build_job_execution_status_context(tab='active')" in routes


def test_execution_subworkspaces_are_demand_loaded() -> None:
    workspace = read('app/templates/jobs/executions/_workspace.html')
    routes = read('app/jobs/routes.py')
    presentation = read('app/jobs/presentation.py')

    assert 'workspace_tabs.render_navigation' in workspace
    assert "selected_job_tab == 'registry'" in workspace
    assert "selected_job_tab == 'queues'" in workspace
    assert 'x-show="activeTab ===' not in workspace
    assert "tab_override=fragment if fragment in {'active', 'registry', 'queues'} else None" in routes
    assert "if selected_tab == 'active':" in presentation
    assert "elif selected_tab == 'registry':" in presentation
    assert 'paginate_query(' in presentation
    assert "elif selected_tab == 'queues':" in presentation


def test_execution_summary_and_queue_activity_use_aggregate_queries() -> None:
    presentation = read('app/jobs/presentation.py')

    assert 'def _execution_summary(' in presentation
    assert "func.count(func.distinct(JobExecution.queue_name)).label('queues')" in presentation
    assert "func.sum(case((active_condition, 1), else_=0)).label('active')" in presentation
    queue_body = presentation.split('def _queue_activity(', 1)[1].split('def _registry_query(', 1)[0]
    assert '.group_by(JobExecution.queue_name)' in queue_body
    assert 'topology = inspect_celery_topology() if aggregates else None' in queue_body
    assert 'query = JobExecution.query.filter(JobExecution.queue_name == queue_name)' not in queue_body


def test_live_polling_is_bounded_and_configuration_has_no_idle_poller() -> None:
    active = read('app/templates/jobs/executions/partials/_active_jobs.html')
    status = read('app/templates/jobs/executions/partials/_status_poller.html')
    configuration = read('app/templates/jobs/configuration/_live_poller.html')
    configuration_service = read('app/jobs/configuration.py')
    workspace = read('app/templates/jobs/executions/_workspace.html')

    assert 'hx-trigger="every 15s"' in active
    assert 'every 30s' in status
    assert "if selected_job_tab != 'active'" in workspace
    assert '_status_oob.html' in active
    assert '{% if include_status_oob|default(false) %}' in active
    assert "fragment_context['include_status_oob'] = fragment == 'active'" in read('app/jobs/routes.py')
    assert active.count('document.hidden') >= 2
    assert 'document.hidden' in status
    assert '{% if selected_job.active_job %}' in configuration
    assert 'hx-trigger="every 10s"' in configuration
    assert 'document.hidden' in configuration
    terminal_refresh = 'if active is None:\n        selected_context = _selected_job_context(definition, policy)'
    assert terminal_refresh in configuration_service
    assert "'The canonical worker execution is still active.'" in configuration_service


def test_execution_registry_uses_canonical_clear_filters_contract() -> None:
    registry = read('app/templates/jobs/executions/partials/_registry.html')

    assert 'components/table_registry.html' in registry
    assert 'table_registry.filter_form' in registry
    assert 'table_registry.clear_filters_link' in registry
    assert 'table_registry.footer' in registry
    assert "query_params={'fragment': 'registry', 'execution_tab': 'registry'}" in registry


def test_jobs_readme_locks_demand_loaded_performance_boundary() -> None:
    readme = read('app/jobs/README.md')

    assert '## Operations UI Performance Contract' in readme
    assert 'must not build hidden workspaces' in readme
    assert 'queue inspection runs only when the Queues view is opened' in readme
    assert 'Job Configuration has no idle polling' in readme
    assert 'Platform Operations → Data Lifecycle' in readme
