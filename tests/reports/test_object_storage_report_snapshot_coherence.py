from datetime import UTC, datetime
from types import SimpleNamespace

from app.reports.export.payloads import object_storage_analysis as reports
from app.storage.object_storage.analytics import service as analytics_service


def test_object_storage_report_reuses_one_pinned_snapshot(monkeypatch) -> None:
    cutoff = datetime(2026, 10, 12, tzinfo=UTC)
    system = SimpleNamespace(
        id='system-a',
        name='storage-uat',
        environment='uat',
        status='active',
        inventory_observed_at=cutoff,
    )
    shared = {'schema': 'object-storage-analytics.v1'}
    state = {'generated_at': cutoff, 'stale': False, 'label': 'Current'}
    seen: list[tuple[str, int]] = []

    def read(*, system_id: str, time_range: str):
        assert system_id == 'system-a'
        assert time_range == '30d'
        return shared, state

    def page(name, args, *, committed_snapshot):
        seen.append((name, id(committed_snapshot[0])))
        assert committed_snapshot[0] is shared
        if name == 'overview':
            return {
                'metrics': {
                    'capacity_total_display': '10 GiB',
                    'usage_total_display': '4 GiB',
                    'capacity_free_display': '6 GiB',
                    'utilization_display': '40%',
                    'bucket_count_display': '1',
                    'object_count_display': '2',
                    'bucket_rows': [{'name': 'logs', 'usage_bytes': 4096}],
                },
                'metrics_source': {'label': 'Ready'},
                'metrics_readiness': {'label': 'Ready'},
                'forecast_materialization': {'label': 'Current'},
            }
        if name == 'performance':
            return {'metrics': {'performance': {'request_rate': '5/s'}}}
        return {'alert_table': {'rows': []}, 'alert_source': {'resolved_label': 'None'}}

    monkeypatch.setattr(reports, 'validate_report_instance', lambda report: None)
    monkeypatch.setattr(reports, 'require_object_storage_system', lambda report: system.id)
    monkeypatch.setattr(
        reports,
        'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda model, key: system)),
    )
    monkeypatch.setattr(reports, 'read_analytics_snapshot', read)
    monkeypatch.setattr(reports, 'get_object_storage_analytics_context', page)
    result = reports.get_report_object_storage_analysis_payload(SimpleNamespace(period='30d'))
    assert [name for name, _ in seen] == ['overview', 'performance', 'alerts']
    assert len({snapshot for _, snapshot in seen}) == 1
    assert result['summary']['usage'] == '4 GiB'
    assert result['data_cutoff'] == cutoff
    assert result['evidence_boundary']['analytics_cutoff'] == cutoff


def test_object_storage_render_path_cannot_dispatch_missing_snapshot(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError('report rendering must not dispatch refresh')

    monkeypatch.setattr(analytics_service, '_queue_analytics_snapshot_refresh', forbidden)
    monkeypatch.setattr(
        analytics_service,
        'analytics_snapshot_blocker',
        lambda *args, **kwargs: {'detail': 'No committed evidence'},
    )
    context = {'metrics_source': {}, 'metrics_readiness': {}}
    result = analytics_service._attach_committed_analytics_snapshot(
        context,
        system=SimpleNamespace(id='system-a'),
        time_range='30d',
        committed_snapshot=(None, {'label': 'Worker Data', 'stale': False}),
    )
    assert result is None
    assert context['analytics_materialization']['refresh_dispatched'] is False
    assert context['dependency_blocker']['detail'] == 'No committed evidence'
