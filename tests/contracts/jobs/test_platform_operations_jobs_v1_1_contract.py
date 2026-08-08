from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_active_work_keeps_polling_after_empty_state() -> None:
    source = _read('app/templates/jobs/executions/partials/_active_jobs.html')

    assert 'hx-trigger="every 5s"' in source
    assert 'hx-sync="this:replace"' in source
    assert '{% if active_job_rows %}hx-get=' not in source
    assert "('Active Attention', job_stats.active_attention)" in source


def test_attention_posture_is_active_plus_recent_terminal_only() -> None:
    source = _read('app/jobs/presentation.py')

    assert "_ACTIVE_ATTENTION_STATUSES = ('retrying', 'cancel_requested')" in source
    assert "_RECENT_ATTENTION_STATUSES = ('failed', 'partially_succeeded', 'expired')" in source
    assert '\n_ATTENTION_STATUSES =' not in source
    assert 'JobExecution.completed_at >= cutoff' in source
    assert 'active_attention + recent_terminal_attention' in source


def test_registry_details_expand_below_row_without_raw_payload() -> None:
    registry = _read('app/templates/jobs/executions/partials/_registry.html')
    detail = _read('app/templates/jobs/executions/partials/_execution_details.html')
    routes = _read('app/jobs/routes.py')

    assert 'components/details/_expandable_row.html' in registry
    assert 'expandable_row.toggle_button(' in registry
    assert "url_for('jobs.execution_details'" in registry
    assert 'data-detail-content' in registry
    assert "@bp.get('/executions/<string:public_id>/details')" in routes
    assert 'present_job_execution_detail(job)' in routes
    for label in (
        'Execution Identity',
        'Scope & Ownership',
        'Lifecycle',
        'Result & Failure Evidence',
        'Result Summary',
    ):
        assert label in detail
    assert 'payload_json' not in detail
    assert 'deduplication_key' not in detail
    assert 'parameter_fingerprint' not in detail


def test_registry_does_not_mix_filtered_count_with_global_metrics() -> None:
    source = _read('app/templates/jobs/executions/partials/_registry.html')

    assert 'job_pagination.total_items' in source
    assert "('Total Records', job_stats.total)" not in source
    assert "('Needs Attention', job_stats.attention)" not in source


def test_queue_worker_readiness_uses_one_shared_topology_snapshot() -> None:
    presentation = _read('app/jobs/presentation.py')
    queue = _read('app/templates/jobs/executions/partials/_queue_activity.html')
    routes = _read('app/jobs/routes.py')

    assert 'topology = inspect_celery_topology() if queue_names else None' in presentation
    assert 'get_queue_readiness(queue_name, topology=topology)' in presentation
    assert 'Worker Readiness' in queue
    assert 'worker_readiness.description' in queue
    assert "fragment='queues'" in queue
    assert "'queues': 'jobs/executions/partials/_queue_activity.html'" in routes
    assert "include_queue_activity=fragment not in {'active', 'registry'}" in routes


def test_jobs_hero_uses_combined_operational_attention() -> None:
    source = _read('app/templates/jobs/index.html')

    assert '{% set operational_attention = job_stats.attention + configuration_stats.attention %}' in source
    assert 'Operational Attention' in source
    assert 'Execution signals and configuration review' in source


def test_v1_1_templates_parse() -> None:
    environment = Environment()
    for relative in (
        'app/templates/jobs/index.html',
        'app/templates/jobs/executions/_workspace.html',
        'app/templates/jobs/executions/partials/_active_jobs.html',
        'app/templates/jobs/executions/partials/_registry.html',
        'app/templates/jobs/executions/partials/_execution_details.html',
        'app/templates/jobs/executions/partials/_queue_activity.html',
    ):
        environment.parse(_read(relative))
