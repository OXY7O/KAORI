from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
EXECUTIONS = ROOT / 'app' / 'templates' / 'jobs' / 'executions'


def _read(relative: str) -> str:
    return (EXECUTIONS / relative).read_text(encoding='utf-8')


def test_tab_counts_refresh_out_of_band_without_page_reload() -> None:
    workspace = _read('_workspace.html')
    status = _read('partials/_status_refresh.html')
    status_oob = _read('partials/_status_oob.html')
    poller = _read('partials/_status_poller.html')
    shared_tabs = (ROOT / 'app' / 'templates' / 'components' / 'workspace_tabs.html').read_text(encoding='utf-8')

    assert 'components/workspace_tabs.html' in workspace
    assert "prefix='execution'" in workspace
    assert 'id="{{ prefix }}-tab-count-{{ tab_key }}"' in shared_tabs
    for key in ('active', 'registry', 'queues'):
        assert f'id="execution-tab-count-{key}"' in status_oob
    assert 'hx-swap-oob="outerHTML"' in status_oob
    assert '_status_oob.html' in status
    assert "fragment='status'" in poller
    assert 'every 30s' in poller
    assert 'class="hidden"' in poller


def test_header_has_no_polling_loading_bar() -> None:
    workspace = _read('_workspace.html')
    active = _read('partials/_active_jobs.html')

    assert 'job-workspace-loading' not in workspace
    assert 'active-job-poll-indicator' in active
    assert 'hx-indicator="#active-job-poll-indicator"' in active
    assert 'class="htmx-indicator hidden"' in active
    assert 'hx-indicator="#active-job-loading"' in active


def test_execution_sections_use_refined_operational_layouts() -> None:
    active = _read('partials/_active_jobs.html')
    registry = _read('partials/_registry.html')
    queues = _read('partials/_queue_activity.html')

    assert "('Active', job_stats.active)" in active
    assert "('Active Attention', job_stats.active_attention)" in active
    assert "('Total Records', job_stats.total)" not in registry
    assert 'View Details' in registry
    assert 'Worker Readiness' in queues
    assert '<table' not in registry
    assert 'overflow-x-auto' not in registry


def test_execution_templates_parse() -> None:
    environment = Environment()
    for relative in (
        '_workspace.html',
        'partials/_active_jobs.html',
        'partials/_registry.html',
        'partials/_queue_activity.html',
        'partials/_status_poller.html',
        'partials/_status_refresh.html',
        'partials/_status_oob.html',
    ):
        environment.parse(_read(relative))
