from __future__ import annotations

from pathlib import Path

from app.reports.schedules.registry import filter_schedule_statement

ROOT = Path(__file__).resolve().parents[3]


def _filters(**overrides: str) -> dict[str, str]:
    result = {
        'search': '',
        'status': '',
        'cadence': '',
        'report_type': '',
        'asset': '',
        'delivery': '',
    }
    result.update(overrides)
    return result


def test_schedule_registry_filter_compiles_to_database_predicates() -> None:
    stmt = filter_schedule_statement(_filters(status='active', cadence='monthly', report_type='tenant_governance'))
    sql = str(stmt)
    assert 'report_schedules.is_enabled' in sql
    assert 'report_schedules.cadence' in sql
    assert 'report_schedules.report_type' in sql


def test_invalid_schedule_filters_stay_sql_false_without_python_side_materialization() -> None:
    for invalid in (
        {'status': 'unsupported'},
        {'asset': 'invalid-asset-key'},
        {'delivery': 'unexpected-channel'},
    ):
        statement = filter_schedule_statement(_filters(**invalid))
        assert 'false' in str(statement).lower()


def test_asset_and_channel_filters_do_not_materialize_python_registry() -> None:
    stmt = filter_schedule_statement(_filters(asset='registry_integration:19', delivery='123'))
    sql = str(stmt)
    assert 'scope_asset_id' in sql
    assert 'notification_channel_ids' in sql


def test_selected_cluster_namespaces_are_permission_bound_and_demand_loaded() -> None:
    routes = (ROOT / 'app/reports/schedules/routes.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/reports/schedules/service.py').read_text(encoding='utf-8')
    js = (ROOT / 'app/static/js/report_schedules.js').read_text(encoding='utf-8')
    support = (ROOT / 'app/reports/schedules/support.py').read_text(encoding='utf-8')
    assert 'def schedule_namespace_options()' in routes
    assert "@permission_required('reports.manage_schedules')" in routes
    assert '_get_namespace_options_by_cluster(selected_cluster_id)' in service
    assert 'get_report_namespace_options_by_cluster(cluster_id) if cluster_id else {}' in support
    assert 'encodeURIComponent(selectedCluster)' in js
    assert 'payload.cluster_id !== selectedCluster' in js


def test_schedule_registry_materializes_only_the_selected_page() -> None:
    service = (ROOT / 'app/reports/schedules/service.py').read_text(encoding='utf-8')
    assert '_serialize_schedule_rows(schedule_records)' in service
    assert '_get_schedule_rows()' not in service
    assert '_get_schedule_counts()' in service
    assert '.limit(200)' in service


def test_stale_namespace_remains_explicit_and_loading_failure_blocks_submit() -> None:
    script = (ROOT / 'app/static/js/report_schedules.js').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/reports/schedules/index.html').read_text(encoding='utf-8')
    assert 'const initialNamespace = namespaceSelect?.value' in script
    assert "unavailable.textContent = initialNamespace + ' · unavailable in current inventory'" in script
    assert 'namespaceSelect?.disabled' in script
    assert 'namespaceError?.classList.remove' in script
    assert 'data-schedule-namespace-error' in template
