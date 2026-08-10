from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/reports/schedules/index.html'
SERVICE = ROOT / 'app/reports/schedules/service.py'
ROUTES = ROOT / 'app/reports/schedules/routes.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_schedules_use_balanced_canonical_hero_actions() -> None:
    template = read(TEMPLATE)

    assert 'data-report-schedules-page="automation-registry-v3"' in template
    assert 'data-schedule-hero-actions="balanced-two"' in template
    assert 'page_hero.context_actions_classes(2)' in template
    assert template.count('page_hero.context_action_classes()') >= 2
    assert 'Create Schedule' in template
    assert 'Job Configuration' in template
    assert 'page_hero.context_actions_classes()' not in template


def test_schedule_registry_and_run_lifecycle_use_framed_canonical_workspaces() -> None:
    template = read(TEMPLATE)
    service = read(SERVICE)

    assert 'components/framed_workspace_tabs.html' in template
    assert 'framed_workspace_tabs.render_navigation(' in template
    assert 'data-schedule-operations-workspace="framed-v3"' in template
    assert "('registry', 'Schedule Registry', 'calendar-range'" in template
    assert "('runs', 'Recent Schedule Runs', 'history'" in template
    assert "payload.active_workspace" in template
    assert "hx_target='#schedule-operations-workspace'" in template
    assert 'components/workspace_tabs.html' not in template
    assert 'x-data="{ tabs:' not in template

    assert 'data-schedule-registry="true"' in template
    assert 'data-schedule-run-registry="lifecycle-v3"' in template
    assert 'components/table_registry.html' in template
    assert template.count("registry_ui.filter_form('reports.schedules'") >= 2
    assert template.count("registry_ui.footer('reports.schedules'") >= 2
    assert "page_param='run_page'" in template
    assert "per_page_param='run_per_page'" in template
    assert 'schedule-registry-loading' in template
    assert 'schedule-runs-loading' in template
    assert 'xl:grid-cols-6' in template
    assert 'xl:grid-cols-5' in template

    assert 'from app.common.pagination import PER_PAGE_OPTIONS, paginate_select, paginate_sequence' in service
    assert 'paginate_sequence(' in service
    assert 'paginate_select(' in service
    assert "query_args.get('run_page', 1)" in service
    assert "query_args.get('run_per_page', PER_PAGE_OPTIONS[0])" in service


def test_schedule_automation_posture_is_state_aware_for_storage_and_worker() -> None:
    template = read(TEMPLATE)
    service = read(SERVICE)

    assert 'data-schedule-posture="automation-v2"' in template
    assert 'data-schedule-control-boundary="true"' in template
    assert 'data-schedule-dependency-readiness="true"' in template
    assert 'data-schedule-storage-ready="true"' in template
    assert 'data-schedule-storage-degraded="true"' in template
    assert 'Artifact Storage Ready' in template
    assert 'Artifact Storage Needs Review' in template
    assert "url_for('reports.storage')" in template
    assert "'automation_posture': get_automation_posture(storage_context, worker_context)" in service
    assert 'def get_automation_posture(' in service
    for label in [
        'Automation Ready',
        'Ready for Unattended Execution',
        'Artifact Execution Paused',
        'Dispatcher Needs Attention',
    ]:
        assert label in service


def test_schedule_tables_and_actions_keep_kaori_contracts() -> None:
    template = read(TEMPLATE)

    for label in [
        'Schedule Registry',
        'Recent Schedule Runs',
        'Schedule Identity & Scope',
        'Report Contract',
        'Schedule Timing',
        'Delivery & State',
        'Execution Guardrail',
        'Delete Report Schedule',
    ]:
        assert label in template

    assert 'table_ui.table_classes()' in template
    assert 'table_ui.head_classes()' in template
    assert 'table_ui.body_classes()' in template
    assert 'table_ui.row_classes()' in template
    assert 'table_ui.cell_classes()' in template
    assert 'data-kaori-dialog-open' in template
    assert 'schedule-form-dialog' in template
    assert 'data-operation-submit' in template
    assert 'data-loading-label="Queueing Report..."' in template
    assert 'data-loading-label="Deleting Schedule..."' in template
    assert 'onsubmit="return confirm(' not in template
    assert 'bg-emerald-' not in template
    assert 'bg-rose-' not in template
    assert 'bg-amber-' not in template
    assert 'bg-slate-' not in template



def test_recent_schedule_runs_are_a_full_server_backed_lifecycle_registry() -> None:
    template = read(TEMPLATE)
    service = read(SERVICE)

    for label in [
        'Recent Schedule Runs',
        'Schedule',
        'Trigger',
        'Result',
        'Period',
        'Delivery',
        'Lifecycle',
        'Schedule Run Detail',
        'Execution Lifecycle',
        'Delivery Evidence',
        'Execution References',
    ]:
        assert label in template

    assert 'data-schedule-run-lifecycle-table="true"' in template
    assert 'run_search' in template
    assert 'run_schedule' in template
    assert 'run_trigger' in template
    assert 'run_status' in template
    assert 'run_period' in template
    assert "'All Retained'" in service
    assert "'30d'" in service
    assert 'def _get_run_registry(' in service
    assert 'def _get_run_selected_filters(' in service
    assert 'def _get_run_filter_options(' in service
    assert 'def _format_run_duration(' in service
    assert '.limit(limit)' in service  # compact summary sampling remains separate from registry paging
    assert 'payload.recent_runs %}' not in template


def test_schedule_feedback_and_run_now_follow_reports_flow() -> None:
    routes = read(ROUTES)

    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in routes
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in routes
    assert "'feedback_delivery': 'toast'" in routes
    assert "title='Report Schedule Created'" in routes
    assert "title='Report Schedule Updated'" in routes
    assert "title='Report Schedule Queued'" in routes
    assert "url_for('reports.generated_reports', focus=report_id, period='all')" in routes
    assert "url_for('reports.generated_report_detail', report_id=report_id)" not in routes
