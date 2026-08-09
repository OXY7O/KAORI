from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/reports/schedules/index.html'
SERVICE = ROOT / 'app/reports/schedules/service.py'
ROUTES = ROOT / 'app/reports/schedules/routes.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_schedules_use_canonical_registry_and_full_width_workspace() -> None:
    template = read(TEMPLATE)
    service = read(SERVICE)

    assert 'components/table_registry.html' in template
    assert "registry_ui.filter_form('reports.schedules'" in template
    assert "registry_ui.footer('reports.schedules'" in template
    assert 'schedule-registry-loading' in template
    assert 'xl:grid-cols-6' in template
    assert 'data-schedule-registry="true"' in template
    assert 'xl:grid-cols-[minmax(0,1fr)_420px]' not in template
    assert '<details class="mt-4 rounded-xl' not in template
    assert 'onsubmit="return confirm(' not in template
    assert 'from app.common.pagination import PER_PAGE_OPTIONS, paginate_sequence' in service
    assert 'paginate_sequence(' in service


def test_schedule_registry_exposes_operational_contract_and_modals() -> None:
    template = read(TEMPLATE)

    for label in [
        'Schedule Automation Posture',
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

    assert 'data-kaori-dialog-open' in template
    assert 'schedule-form-dialog' in template
    assert 'data-operation-submit' in template
    assert 'data-loading-label="Queueing Report..."' in template
    assert 'data-loading-label="Deleting Schedule..."' in template
    assert 'bg-emerald-' not in template
    assert 'bg-rose-' not in template
    assert 'bg-amber-' not in template
    assert 'bg-slate-' not in template


def test_schedule_filter_and_rows_state_are_canonical() -> None:
    template = read(TEMPLATE)
    service = read(SERVICE)

    for name in ['search', 'status', 'cadence', 'report_type', 'cluster', 'delivery']:
        assert f'name="{name}"' in template

    assert "'registry_query_params':" in service
    assert "'per_page_options': list(PER_PAGE_OPTIONS)" in service
    assert "'selected_filters': selected_filters" in service
    assert "'filter_options': _get_schedule_filter_options" in service
    assert "'page': payload.pagination.page" in template
    assert "'per_page': payload.pagination.per_page" in template


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
