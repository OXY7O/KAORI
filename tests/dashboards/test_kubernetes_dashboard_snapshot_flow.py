from __future__ import annotations

from types import SimpleNamespace

from app.analytics import job_adapter
from app.dashboards.kubernetes import service, snapshot_builder
from app.dashboards.kubernetes.schema import AlertsSnapshot, CapacityItem, CapacitySnapshot, InventorySnapshot
from app.dashboards.kubernetes.sections.cluster_health import build_cluster_health
from app.dashboards.kubernetes.sections.forecast import build_forecast_snapshot
from app.dashboards.kubernetes.snapshot_builder import build_dashboard_alerts_context


def _scope_with_selected():
    cluster = SimpleNamespace(id='cluster-1', name='Primary')
    option = SimpleNamespace(id='cluster-1', name='Primary')
    return {}, [cluster], [option], 'cluster-1', cluster


def test_dashboard_shell_never_reads_analytics_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(service, '_scope', lambda _selected: _scope_with_selected())
    monkeypatch.setattr(service, '_inventory_snapshot', lambda _models, _selected: InventorySnapshot())
    monkeypatch.setattr(service, '_latest_inventory_sync', lambda _models, _selected: None)
    monkeypatch.setattr(service, 'build_reporting_snapshot', lambda **_kwargs: SimpleNamespace())

    def unexpected_snapshot_read(*_args, **_kwargs):
        raise AssertionError('The dashboard shell must not read analytics snapshots.')

    monkeypatch.setattr(service, '_capacity_signal', unexpected_snapshot_read)
    monkeypatch.setattr(service, '_alerts_signal', unexpected_snapshot_read)
    monkeypatch.setattr(service, '_top_consumers_signal', unexpected_snapshot_read)
    monkeypatch.setattr(service, '_forecast_signal', unexpected_snapshot_read)

    dashboard = service.get_dashboard_overview(selected_cluster_id='cluster-1')

    assert dashboard.selected_cluster_id == 'cluster-1'
    assert dashboard.inventory_snapshot.pods == 0


def test_capacity_section_reads_only_committed_capacity_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(service, '_scope', lambda _selected: _scope_with_selected())
    capacity = CapacitySnapshot(
        items=[CapacityItem(label='CPU', used_percent=42.0, headroom_percent=58.0, description='snapshot')],
        source_status='Available',
    )
    monkeypatch.setattr(service, '_capacity_signal', lambda _cluster: (capacity, SimpleNamespace(state='fresh')))

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError('Unrelated dashboard snapshots must not be read for the capacity section.')

    monkeypatch.setattr(service, '_alerts_signal', unexpected_read)
    monkeypatch.setattr(service, '_top_consumers_signal', unexpected_read)
    monkeypatch.setattr(service, '_forecast_signal', unexpected_read)
    monkeypatch.setattr(service, '_inventory_snapshot', unexpected_read)

    dashboard = service.get_dashboard_section('capacity_snapshot', selected_cluster_id='cluster-1')

    assert dashboard.capacity_snapshot.source_status == 'Available'
    assert dashboard.capacity_snapshot.items[0].used_percent == 42.0


def test_cluster_health_reads_capacity_and_alert_snapshots_only(monkeypatch) -> None:
    monkeypatch.setattr(service, '_scope', lambda _selected: _scope_with_selected())
    monkeypatch.setattr(
        service,
        '_capacity_signal',
        lambda _cluster: (CapacitySnapshot(source_status='Available'), SimpleNamespace(state='fresh')),
    )
    monkeypatch.setattr(
        service,
        '_alerts_signal',
        lambda _cluster: (AlertsSnapshot(critical=1, source_status='Available'), SimpleNamespace(state='fresh')),
    )

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError('Cluster health must not read top-consumer or forecast snapshots.')

    monkeypatch.setattr(service, '_top_consumers_signal', unexpected_read)
    monkeypatch.setattr(service, '_forecast_signal', unexpected_read)
    monkeypatch.setattr(service, 'query_for_clusters', lambda _model, _cluster_ids: [])
    captured: dict[str, object] = {}

    def capture_cluster_health(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(service, 'build_cluster_health', capture_cluster_health)

    dashboard = service.get_dashboard_section('cluster_health', selected_cluster_id='cluster-1')

    assert dashboard.cluster_health_snapshot == []
    assert captured['capacity_by_cluster']['cluster-1'].source_status == 'Available'
    assert captured['alerts_by_cluster']['cluster-1'].critical == 1
    assert captured['nodes_by_cluster'] == {}
    assert captured['pods_by_cluster'] == {}


def test_cluster_health_reads_endpoint_from_canonical_kubernetes_connection() -> None:
    cluster = SimpleNamespace(
        id='cluster-1',
        name='Primary',
        status='connected',
        kubernetes_connection=SimpleNamespace(server='https://k8s.example.test:6443'),
    )

    rows = build_cluster_health(clusters_raw=[cluster], selected_cluster_id=None)

    assert len(rows) == 1
    assert rows[0].cluster_endpoint == 'https://k8s.example.test:6443'


def test_cluster_health_does_not_read_removed_cluster_server_field() -> None:
    cluster = SimpleNamespace(
        id='cluster-1',
        name='Primary',
        status='connected',
        server='https://legacy.example.test:6443',
        kubernetes_connection=None,
    )

    rows = build_cluster_health(clusters_raw=[cluster], selected_cluster_id=None)

    assert rows[0].cluster_endpoint == 'Endpoint unavailable'


def test_alert_materialization_builds_compact_worker_payload(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1')
    monkeypatch.setattr(
        snapshot_builder,
        'Cluster',
        SimpleNamespace(query=SimpleNamespace(get=lambda _cluster_id: cluster)),
    )
    monkeypatch.setattr(
        'app.dashboards.kubernetes.snapshot_builder.load_alerts_by_source',
        lambda **_kwargs: (
            [
                {'name': 'CriticalA', 'severity': 'critical', 'status': 'firing', 'summary': 'A'},
                {'name': 'WarningB', 'severity': 'warning', 'status': 'pending', 'summary': 'B'},
                {'name': 'InfoC', 'severity': 'info', 'status': 'active', 'summary': 'C'},
                {'name': 'ResolvedD', 'severity': 'critical', 'status': 'resolved', 'summary': 'D'},
            ],
            {'connected': True, 'resolved_source': 'alertmanager'},
        ),
    )

    context = build_dashboard_alerts_context({'cluster_id': 'cluster-1'})

    assert context['critical'] == 1
    assert context['warning'] == 1
    assert context['info'] == 1
    assert [item['title'] for item in context['items']] == ['CriticalA', 'WarningB', 'InfoC']
    assert context['source_connected'] is True


def test_scheduled_analytics_work_items_include_dashboard_and_page_alert_snapshots(monkeypatch) -> None:
    policy = SimpleNamespace(
        configuration_json={
            'time_ranges': ['24h'],
            'freshness_minutes': 20,
            'stale_grace_minutes': 1440,
        }
    )
    cluster = SimpleNamespace(id='cluster-1')

    monkeypatch.setattr(job_adapter, '_dataset_eligible', lambda *_args: True)

    work_items = job_adapter._analytics_work_items(
        policy,
        None,
        clusters=[cluster],
        only_due=False,
    )

    alert_items = [
        item for item in work_items
        if item['dataset_key'] in {'dashboard.kubernetes.alerts', 'analytics.alerts'}
    ]
    assert [item['dataset_key'] for item in alert_items] == [
        'dashboard.kubernetes.alerts',
        'analytics.alerts',
    ]
    assert alert_items[0]['parameters'] == {'cluster_id': 'cluster-1'}
    assert alert_items[1]['parameters'] == {
        'cluster_id': 'cluster-1',
        'source': 'auto',
    }
    assert [item['stale_grace_minutes'] for item in alert_items] == [30, 30]


def test_alertmanager_only_cluster_schedules_alert_snapshots(monkeypatch) -> None:
    policy = SimpleNamespace(
        configuration_json={
            'time_ranges': ['24h'],
            'freshness_minutes': 20,
            'stale_grace_minutes': 1440,
        }
    )
    cluster = SimpleNamespace(id='alert-only')

    monkeypatch.setattr(job_adapter, '_dataset_eligible', lambda *_args: True)

    work_items = job_adapter._analytics_work_items(
        policy,
        None,
        clusters=[cluster],
        only_due=False,
        prometheus_cluster_ids=set(),
    )

    assert [item['dataset_key'] for item in work_items] == [
        'dashboard.kubernetes.alerts',
        'analytics.alerts',
    ]


def test_dashboard_required_analytics_snapshots_use_canonical_dimensions(monkeypatch) -> None:
    policy = SimpleNamespace(
        configuration_json={
            'time_ranges': ['7d'],
            'freshness_minutes': 20,
            'stale_grace_minutes': 1440,
        }
    )
    cluster = SimpleNamespace(id='cluster-1')

    monkeypatch.setattr(job_adapter, '_dataset_eligible', lambda *_args: True)

    work_items = job_adapter._analytics_work_items(
        policy,
        None,
        clusters=[cluster],
        only_due=False,
    )

    by_key = {}
    for item in work_items:
        by_key.setdefault(item['dataset_key'], []).append(item['parameters'])

    assert {'cluster_id': 'cluster-1', 'time_range': '24h'} in by_key['analytics.capacity']
    assert by_key['analytics.storage'] == [{'cluster_id': 'cluster-1'}]
    assert by_key['analytics.top_consumers'] == [{'cluster_id': 'cluster-1'}]


def test_analytics_policy_precomputes_only_selected_utilization_trends(monkeypatch) -> None:
    policy = SimpleNamespace(
        configuration_json={
            'time_ranges': ['24h'],
            'freshness_minutes': 20,
            'stale_grace_minutes': 1440,
        }
    )
    cluster = SimpleNamespace(id='cluster-1')

    monkeypatch.setattr(job_adapter, '_dataset_eligible', lambda *_args: True)

    work_items = job_adapter._analytics_work_items(
        policy,
        None,
        clusters=[cluster],
        only_due=False,
    )

    trend_parameters = [
        item['parameters']
        for item in work_items
        if item['dataset_key'] == 'analytics.utilization.trend'
    ]
    assert trend_parameters == [
        {'cluster_id': 'cluster-1', 'trend_hours': '24'},
    ]


def test_forecast_history_snapshots_are_materialized_without_ui_projection_dimensions(monkeypatch) -> None:
    policy = SimpleNamespace(
        configuration_json={
            'history_windows': ['90d'],
            'freshness_minutes': 120,
            'stale_grace_minutes': 4320,
        }
    )
    cluster = SimpleNamespace(id='cluster-1')

    monkeypatch.setattr(job_adapter, '_prometheus_dataset_eligible', lambda *_args: True)

    work_items = job_adapter._forecast_work_items(
        policy,
        None,
        clusters=[cluster],
        only_due=False,
    )

    assert [item['parameters'] for item in work_items] == [
        {'cluster_id': 'cluster-1', 'history_window': '30d'},
        {'cluster_id': 'cluster-1', 'history_window': '90d'},
    ]


def test_cluster_health_preloads_visible_inventory_with_two_set_queries(monkeypatch) -> None:
    clusters = [
        SimpleNamespace(id='cluster-1', name='Primary'),
        SimpleNamespace(id='cluster-2', name='Secondary'),
    ]
    options = [SimpleNamespace(id=cluster.id, name=cluster.name) for cluster in clusters]
    node_model = object()
    pod_model = object()
    models = {'NodeInventory': node_model, 'PodInventory': pod_model}
    monkeypatch.setattr(
        service,
        '_scope',
        lambda _selected: (models, clusters, options, None, None),
    )
    monkeypatch.setattr(
        service,
        '_capacity_signal',
        lambda _cluster: (CapacitySnapshot(source_status='Available'), SimpleNamespace(state='fresh')),
    )
    monkeypatch.setattr(
        service,
        '_alerts_signal',
        lambda _cluster: (AlertsSnapshot(source_status='Available'), SimpleNamespace(state='fresh')),
    )
    query_calls: list[tuple[object, list[str]]] = []

    def capture_query(model, cluster_ids):
        query_calls.append((model, cluster_ids))
        if model is node_model:
            return [SimpleNamespace(cluster_id='cluster-1')]
        return [SimpleNamespace(cluster_id='cluster-2')]

    monkeypatch.setattr(service, 'query_for_clusters', capture_query)
    captured: dict[str, object] = {}
    monkeypatch.setattr(service, 'build_cluster_health', lambda **kwargs: captured.update(kwargs) or [])

    service.get_dashboard_section('cluster_health')

    assert query_calls == [
        (node_model, ['cluster-1', 'cluster-2']),
        (pod_model, ['cluster-1', 'cluster-2']),
    ]
    assert list(captured['nodes_by_cluster']) == ['cluster-1']
    assert list(captured['pods_by_cluster']) == ['cluster-2']


def test_dashboard_forecast_snapshot_exposes_chart_values_and_horizon() -> None:
    snapshot = build_forecast_snapshot(
        context={
            'forecast_payload': {
                'has_data': True,
                'horizon_days': 60,
                'summary': {
                    'highest_projected_label': 'Memory',
                    'highest_projected_percent': 92,
                },
                'items': [
                    {
                        'key': 'cpu',
                        'label': 'CPU Growth',
                        'status_label': 'Warning',
                        'current_percent': 61.0,
                        'projected_percent': 78.4,
                        'historical_points': [
                            {'percent': 48.0},
                            {'percent': 55.0},
                            {'percent': 61.0},
                        ],
                        'forecast_points': [
                            {'percent': 67.0},
                            {'percent': 72.0},
                            {'percent': 78.4},
                        ],
                        'icon': 'cpu',
                    },
                    {
                        'key': 'memory',
                        'label': 'Memory Growth',
                        'status_label': 'Critical',
                        'current_percent': 74.0,
                        'projected_percent': 92,
                        'historical_points': [
                            {'percent': 66.0},
                            {'percent': 70.0},
                            {'percent': 74.0},
                        ],
                        'forecast_points': [
                            {'percent': 80.0},
                            {'percent': 86.0},
                            {'percent': 92.0},
                        ],
                        'icon': 'memory-stick',
                    },
                ],
            }
        },
        unavailable_reason='Forecast unavailable.',
    )

    assert snapshot.source_status == 'Available'
    assert snapshot.horizon_days == 60
    assert [item.projected_percent for item in snapshot.items] == [78.4, 92.0]
    assert [item.current_percent for item in snapshot.items] == [61.0, 74.0]
    assert all(item.historical_points for item in snapshot.items)
    assert all(item.forecast_points for item in snapshot.items)
    assert snapshot.item_count == 2
    assert snapshot.at_risk_count == 2
    assert snapshot.critical_count == 1
    assert snapshot.highest_projected_label == 'Memory'
    assert snapshot.highest_projected_percent == 92.0
    assert snapshot.has_historical_series is True
    assert snapshot.insight == 'Memory has the highest 60-day projection at 92%.'
