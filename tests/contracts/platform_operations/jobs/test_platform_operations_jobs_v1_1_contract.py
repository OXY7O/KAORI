from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_active_work_keeps_polling_after_empty_state() -> None:
    source = _read('app/templates/platform_operations/jobs/executions/partials/_active_jobs.html')

    assert 'hx-trigger="every 15s"' in source
    assert 'hx-sync="this:replace"' in source
    assert '{% if active_job_rows %}hx-get=' not in source
    assert "('Active Attention', job_stats.active_attention)" in source


def test_attention_posture_is_active_plus_recent_terminal_only() -> None:
    source = _read('app/platform_operations/jobs/presentation.py')

    assert "_ACTIVE_ATTENTION_STATUSES = ('retrying', 'cancel_requested')" in source
    assert "_RECENT_ATTENTION_STATUSES = ('failed', 'partially_succeeded', 'expired')" in source
    assert '\n_ATTENTION_STATUSES =' not in source
    assert 'JobExecution.completed_at >= cutoff' in source
    assert 'active_attention + recent_attention' in source


def test_registry_details_use_shared_modal_without_raw_payload() -> None:
    registry = _read('app/templates/platform_operations/jobs/executions/partials/_registry.html')
    detail = _read('app/templates/platform_operations/jobs/executions/partials/_execution_details.html')
    routes = _read('app/platform_operations/jobs/routes.py')

    assert 'components/resource_detail_modal.html' in registry
    assert 'resource_detail_modal.detail_button(' in registry
    assert 'resource_detail_modal.host(' in registry
    assert "url_for('jobs.execution_details'" in registry
    assert 'data-resource-detail-header' in detail
    assert 'data-resource-detail-summary' in detail
    assert 'data-kaori-detail-variant="job-execution"' in detail
    assert 'data-kaori-detail-variant' in _read('app/static/js/detail_rows.js')
    assert 'progress_bar.job_progress' in detail
    assert 'detail.inventory_fact_grid(execution.result_summary, columns=2)' in detail
    assert 'execution.error_code' in detail
    assert 'execution.error_message' in detail
    assert 'data-resource-detail-header' in detail.split('data-resource-detail-summary', 1)[0]
    assert "@bp.get('/executions/<string:public_id>/details')" in routes
    assert 'present_job_execution_detail(job)' in routes
    for label in (
        'Execution Snapshot',
        'Execution Outcome',
        'Execution Context',
        'Lifecycle Timeline',
        'Committed Result Evidence',
        'Technical References',
    ):
        assert label in detail
    assert 'payload_json' not in detail
    assert 'deduplication_key' not in detail
    assert 'parameter_fingerprint' not in detail


def test_registry_does_not_mix_filtered_count_with_global_metrics() -> None:
    source = _read('app/templates/platform_operations/jobs/executions/partials/_registry.html')

    assert 'job_pagination.total_items' in source
    assert "('Total Records', job_stats.total)" not in source
    assert "('Needs Attention', job_stats.attention)" not in source


def test_queue_worker_readiness_uses_one_shared_topology_snapshot() -> None:
    presentation = _read('app/platform_operations/jobs/presentation.py')
    queue = _read('app/templates/platform_operations/jobs/executions/partials/_queue_activity.html')
    routes = _read('app/platform_operations/jobs/routes.py')

    assert 'queue_names.update(definition.queue_name for definition in list_job_definitions())' in presentation
    assert 'topology = inspect_celery_topology() if queue_names else None' in presentation
    assert 'get_queue_readiness(queue_name, topology=topology)' in presentation
    assert 'Worker Readiness' in queue
    assert 'worker_readiness.description' in queue
    assert "fragment='queues'" in queue
    assert "'queues': 'platform_operations/jobs/executions/partials/_queue_activity.html'" in routes
    assert "tab_override=fragment if fragment in {'active', 'registry', 'queues'} else None" in routes


def test_jobs_hero_uses_combined_operational_attention() -> None:
    source = _read('app/templates/platform_operations/jobs/index.html')

    assert '{% set operational_attention = job_stats.attention + configuration_stats.attention %}' in source
    assert 'Operational Attention' in source
    assert 'Execution signals and configuration review' in source


def test_v1_1_templates_parse() -> None:
    environment = Environment()
    for relative in (
        'app/templates/platform_operations/jobs/index.html',
        'app/templates/platform_operations/jobs/executions/_workspace.html',
        'app/templates/platform_operations/jobs/executions/partials/_active_jobs.html',
        'app/templates/platform_operations/jobs/executions/partials/_registry.html',
        'app/templates/platform_operations/jobs/executions/partials/_execution_details.html',
        'app/templates/platform_operations/jobs/executions/partials/_queue_activity.html',
    ):
        environment.parse(_read(relative))


def test_registry_detail_outcome_first_keeps_success_and_failure_truthful() -> None:
    detail = _read('app/templates/platform_operations/jobs/executions/partials/_execution_details.html')
    presentation = _read('app/common/job_execution_presentation.py')
    assert "execution.error_code != '-'" in detail
    assert "execution.error_message != 'No execution error was recorded.'" in detail
    assert 'Recorded Error Evidence' in detail
    assert 'Committed worker state and last recorded progress.' in detail
    assert 'No Result Summary Recorded' in detail
    assert 'result_summary_remaining' in detail
    assert 'Execution ID' in detail
    assert 'Celery Task ID' in detail
    assert 'Parent Execution' in detail
    assert 'Result Reference' in detail
    assert "'error_message': job.error_message or 'No execution error was recorded.'" in presentation
    assert 'payload_json' not in detail


def test_registry_detail_density_uses_one_sheet_and_progressive_disclosure() -> None:
    source = _read('app/templates/platform_operations/jobs/executions/partials/_execution_details.html')
    view_more = _read('app/templates/components/view_more_content.html')

    assert '{% call detail.resource_sheet() %}' in source
    assert 'detail.detail_card(' not in source
    assert '{% call view_more.render(' in source
    assert "'Additional Execution Evidence'" in source
    assert "closed_label='View More'" in source
    assert "open_label='View Less'" in source
    assert 'data-kaori-detail-variant="job-execution"' in source
    assert 'data-resource-detail-header' in source
    assert 'data-resource-detail-summary' in source
    assert 'detail.inventory_fact_grid(execution.result_summary, columns=2)' in source
    assert '<details class="group' in view_more
    assert 'focus-visible:ring-2' in view_more


def test_registry_detail_primary_facts_and_timeline_are_responsive() -> None:
    source = _read('app/templates/platform_operations/jobs/executions/partials/_execution_details.html')

    assert 'data-kaori-inventory-fact-grid' in _read('app/templates/components/details/_detail_content.html')
    assert "('Requested By', execution.requester)" in source
    assert "('Provider', execution.provider_label)" in source
    assert "('Queue', execution.queue_name)" in source
    assert "('Scope', execution.scope)" in source
    assert 'aria-label="Committed execution milestones"' in source
    for key in ('queued_at', 'started_at', 'completed_at'):
        assert f'execution.{key}' in source
    for key in ('heartbeat_at', 'cancel_requested_at', 'updated_at', 'expires_at'):
        assert f'execution.{key}' in source
    for label in ('Technical References', 'Execution ID', 'Celery Task ID', 'Result Reference'):
        assert label in source
    assert 'columns=2' in source
    assert 'sm:grid-cols-3' in source
    assert 'progress_bar.job_progress' in source
    assert 'payload_json' not in source
    assert 'deduplication_key' not in source
