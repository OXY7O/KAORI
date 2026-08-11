from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from flask import Flask

from app.analytics import tasks
from app.analytics.common import context as common_context
from app.analytics.forecast import presentation as forecast_presentation
from app.analytics.materialization import requests as materialization_requests
from app.analytics.materialization.catalog import canonical_parameters, get_dataset
from app.analytics.materialization.presentation import pending_page_context
from app.analytics.materialization.requests import MaterializedRequest
from app.analytics.materialization.service import SnapshotResult, store_snapshot
from app.integrations.prometheus.query_profiles.audit import PromQLProfileAuditor
from app.jobs.definitions.forecast_refresh import FORECAST_REFRESH_DEFINITION
from app.prometheus.presentation import _MODULE_REQUIREMENTS, _RESOLUTION_CONSUMERS, _module_readiness_rows


def test_snapshot_parameters_exclude_view_only_filters() -> None:
    assert canonical_parameters(
        'analytics.storage',
        {
            'cluster_id': 'cluster-1',
            'time_range': '60d',
            'namespace': 'payments',
            'search': 'claim-a',
            'page': 7,
        },
    ) == {'cluster_id': 'cluster-1'}

    assert canonical_parameters(
        'analytics.workload',
        {
            'cluster_id': 'cluster-1',
            'time_range': '7d',
            'namespace': 'payments',
            'status': 'warning',
            'page': 3,
        },
    ) == {
        'cluster_id': 'cluster-1',
        'time_range': '7d',
    }

    assert canonical_parameters(
        'analytics.top_consumers',
        {
            'cluster_id': 'cluster-1',
            'namespace': 'payments',
            'tab': 'cpu',
            'time_range': '30d',
            'search': 'api',
        },
    ) == {
        'cluster_id': 'cluster-1',
        'namespace': 'payments',
    }

    assert canonical_parameters(
        'analytics.forecast',
        {
            'cluster_id': 'cluster-1',
            'history_window': '30d',
            'forecast_horizon': '365d',
            'resource': 'memory',
            'method': 'conservative',
            'namespace': 'payments',
        },
    ) == {
        'cluster_id': 'cluster-1',
        'history_window': '30d',
        'namespace': 'payments',
    }


def test_forecast_policy_materializes_history_only() -> None:
    configuration = FORECAST_REFRESH_DEFINITION.default_configuration or {}

    assert configuration['history_windows'] == ['7d', '30d', '90d']
    assert 'forecast_horizons' not in configuration


def test_snapshot_store_rejects_dependency_blockers_before_database_write() -> None:
    with pytest.raises(ValueError, match='contains a dependency blocker'):
        store_snapshot(
            cluster_id='cluster-1',
            dataset_key='analytics.storage',
            parameters={'cluster_id': 'cluster-1'},
            context={'dependency_blocker': {'kind': 'prometheus_capability'}},
            job_execution_id=None,
        )


def test_storage_and_workload_capability_contracts_match_worker_services() -> None:
    storage = get_dataset('analytics.storage')
    workload = get_dataset('analytics.workload')

    assert storage.required_binding_capabilities == ('metrics', 'storage')
    assert workload.required_binding_capabilities == ('metrics', 'workload')

    assert storage.required_capabilities == (
        'instant_query',
        'kubernetes_identity',
        'pvc_usage',
        'node_filesystem_identity',
    )
    assert 'range_query' not in storage.required_capabilities

    assert workload.required_capabilities == (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'workload_metrics',
        'resource_requests_limits',
    )

    assert _MODULE_REQUIREMENTS['app.analytics.storage'] == storage.required_capabilities
    assert _MODULE_REQUIREMENTS['app.analytics.workload'] == workload.required_capabilities

    consumers = {item['key']: item for item in _RESOLUTION_CONSUMERS}
    assert consumers['storage']['binding_capabilities'] == storage.required_binding_capabilities
    assert consumers['workload']['binding_capabilities'] == workload.required_binding_capabilities
    assert consumers['storage']['technical_capabilities'] == storage.required_capabilities
    assert consumers['workload']['technical_capabilities'] == workload.required_capabilities


def test_ready_prometheus_reports_query_gaps_as_degraded_not_unavailable() -> None:
    persisted = PromQLProfileAuditor._module_readiness(
        {
            'app.analytics.storage': {
                'ready_count': 0,
                'query_count': 4,
                'blocked_count': 4,
            }
        }
    )
    assert persisted['app.analytics.storage']['status'] == 'degraded'

    instance = SimpleNamespace(
        module_readiness=persisted,
        last_validated_at=object(),
    )
    rows = _module_readiness_rows(
        instance,
        available_capabilities=set(_MODULE_REQUIREMENTS['app.analytics.storage']),
    )
    storage = next(item for item in rows if item['key'] == 'app.analytics.storage')
    assert storage['status'] == 'degraded'
    assert storage['missing_required_labels'] == []
    assert storage['blocked_count'] == 4


def test_persisted_readiness_builds_query_service_without_live_health_probe(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1', name='Primary')
    instance = SimpleNamespace(
        endpoint='http://prometheus:9090',
        last_status='connected',
        last_response_time_ms=18,
        last_error=None,
        last_checked_at=None,
    )
    selected = SimpleNamespace(
        instance=instance,
        operational_state='healthy',
        decision_reason='Source is healthy.',
    )
    ordered_field = SimpleNamespace(asc=lambda: object())
    monkeypatch.setattr(
        common_context,
        'Cluster',
        SimpleNamespace(
            query=SimpleNamespace(
                order_by=lambda *_args: SimpleNamespace(all=lambda: [cluster]),
            ),
            created_at=ordered_field,
            id=ordered_field,
        ),
    )
    monkeypatch.setattr(common_context, 'get_selected_cluster', lambda **_kwargs: cluster)
    monkeypatch.setattr(common_context, 'resolve_instance_for_cluster', lambda _cluster_id: instance)
    monkeypatch.setattr(
        common_context,
        'resolve_prometheus_sources',
        lambda **_kwargs: SimpleNamespace(selected=selected, candidates=(selected,)),
    )
    prometheus_marker = object()
    utilization_marker = object()
    monkeypatch.setattr(common_context, 'PrometheusService', lambda *_args, **_kwargs: prometheus_marker)
    monkeypatch.setattr(
        common_context,
        'UtilizationService',
        lambda prometheus: utilization_marker if prometheus is prometheus_marker else None,
    )

    _clusters, selected_cluster, utilization, context = common_context.build_analysis_utilization_context(
        {'cluster_id': 'cluster-1'},
        check_prometheus_connection=False,
    )

    assert selected_cluster is cluster
    assert utilization is utilization_marker
    assert context['dependency_blocker'] is None
    assert context['prometheus_connected'] is True
    assert context['prometheus_status']['response_time_ms'] == 18


def test_forecast_selectors_reproject_committed_history_locally(monkeypatch) -> None:
    monkeypatch.setattr(forecast_presentation, 'build_forecast_actionable_recommendations', lambda _payload: [])
    monkeypatch.setattr(forecast_presentation, 'format_recommendation_cards', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(forecast_presentation, 'count_actionable_recommendations', lambda _items: 0)

    context = {
        'namespace_options': [],
        'forecast_payload': {
            'items': [
                {
                    'key': 'cpu',
                    'label': 'CPU',
                    'unit': 'cores',
                    'capacity': 10.0,
                    'historical_points': [
                        {'date': '2026-07-01', 'value': 2.0, 'percent': 20.0},
                        {'date': '2026-07-02', 'value': 2.5, 'percent': 25.0},
                        {'date': '2026-07-03', 'value': 3.0, 'percent': 30.0},
                    ],
                }
            ]
        },
    }

    result = forecast_presentation.present_forecast_materialized_context(
        context,
        {
            'history_window': '30d',
            'forecast_horizon': '180d',
            'tab': 'cpu',
            'method': 'conservative',
        },
    )

    assert result['selected_forecast_horizon'] == '180d'
    assert result['selected_tab'] == 'cpu'
    assert result['selected_method'] == 'conservative'
    assert len(result['forecast_payload']['items']) == 1
    assert len(result['forecast_payload']['items'][0]['forecast_points']) == 180
    assert result['forecast_payload']['items'][0]['forecast_method'] == 'conservative'


def test_prometheus_dataset_binding_gap_is_advisory_after_query_transport_is_ready(monkeypatch) -> None:
    cluster = SimpleNamespace(id='cluster-1', name='Primary')
    ready = SimpleNamespace(
        missing_binding_capabilities=(),
        missing_technical_capabilities=(),
        operational_state='healthy',
        decision_reason='Query transport is ready.',
    )
    strict_candidate = SimpleNamespace(
        missing_binding_capabilities=('storage',),
        missing_technical_capabilities=(),
        operational_state='healthy',
        decision_reason='Missing binding coverage: storage.',
    )

    def resolve_sources(**kwargs):
        if kwargs['required_binding_capabilities'] == ('metrics',):
            return SimpleNamespace(selected=ready, candidates=(ready,))
        return SimpleNamespace(selected=None, candidates=(strict_candidate,))

    monkeypatch.setattr(materialization_requests, 'resolve_prometheus_sources', resolve_sources)
    monkeypatch.setattr(
        materialization_requests,
        'prometheus_capability_blocker',
        lambda _cluster, **kwargs: {
            'kind': 'prometheus_capability',
            'labels': kwargs['capability_labels'],
            'feature': kwargs['feature_label'],
        },
    )

    blocker, warning = materialization_requests._prometheus_dependency_state(
        dataset_key='analytics.storage',
        cluster=cluster,
    )

    assert blocker is None
    assert warning == {
        'kind': 'prometheus_capability',
        'labels': ['Storage'],
        'feature': 'Storage Analysis',
    }


def test_prometheus_alert_fallback_reports_capability_gap_not_connection_failure(
    monkeypatch,
) -> None:
    cluster = SimpleNamespace(id='cluster-1', name='Primary')
    candidate = SimpleNamespace(
        missing_binding_capabilities=('alert_metrics',),
        missing_technical_capabilities=('kubernetes_identity',),
        decision_reason='Missing capability evidence.',
    )
    monkeypatch.setattr(
        materialization_requests,
        'resolve_alertmanager_sources',
        lambda **_kwargs: SimpleNamespace(selected=None, candidates=()),
    )
    monkeypatch.setattr(
        materialization_requests,
        'resolve_prometheus_sources',
        lambda **_kwargs: SimpleNamespace(selected=None, candidates=(candidate,)),
    )
    monkeypatch.setattr(
        materialization_requests,
        'prometheus_capability_blocker',
        lambda _cluster, **kwargs: {
            'kind': 'prometheus_capability',
            'labels': kwargs['capability_labels'],
            'feature': kwargs['feature_label'],
        },
    )

    blocker = materialization_requests._alert_dependency_blocker(
        cluster=cluster,
        selected_source='prometheus',
    )

    assert blocker == {
        'kind': 'prometheus_capability',
        'labels': ['Alert Metrics', 'Kubernetes Identity Metrics'],
        'feature': 'Alerts & Anomalies',
    }


def test_dependency_blocker_is_failed_instead_of_committed(monkeypatch) -> None:
    failed: list[tuple[str, str]] = []
    stored: list[bool] = []

    class Lifecycle:
        def __init__(self, _task_id: str) -> None:
            pass

        def start(self, **_kwargs) -> None:
            pass

        def checkpoint(self, **_kwargs) -> None:
            pass

        def fail(self, *_args, **_kwargs) -> None:
            pass

        def succeed(self, **_kwargs) -> None:
            pass

        def canceled(self) -> None:
            pass

    dataset = SimpleNamespace(
        label='Storage Analysis',
        freshness_minutes=20,
        stale_grace_minutes=1440,
        builder=lambda _parameters: {
            'dependency_blocker': {
                'title': 'Storage capability incomplete',
                'description': 'PVC evidence is unavailable.',
            }
        },
    )
    monkeypatch.setattr(tasks, '_task_id', lambda *_args, **_kwargs: 'task-1')
    monkeypatch.setattr(tasks, 'JobExecutionContext', Lifecycle)
    monkeypatch.setattr(tasks, 'get_dataset', lambda _key: dataset)
    monkeypatch.setattr(
        tasks,
        'Cluster',
        SimpleNamespace(query=SimpleNamespace(get=lambda _cluster_id: SimpleNamespace(name='Primary'))),
    )
    monkeypatch.setattr(
        tasks,
        'fail_snapshot',
        lambda **kwargs: failed.append((kwargs['dataset_key'], str(kwargs['error']))),
    )
    monkeypatch.setattr(tasks, 'store_snapshot', lambda **_kwargs: stored.append(True))
    monkeypatch.setattr(tasks, 'mark_snapshot_pending', lambda **_kwargs: None)
    monkeypatch.setattr(tasks, 'analytics_source_lock', lambda **_kwargs: nullcontext(0))
    monkeypatch.setattr(tasks.db, 'session', SimpleNamespace(rollback=lambda: None))

    app = Flask(__name__)
    with app.app_context():
        result = tasks._materialize(
            job_execution_id=11,
            work_items=[
                {
                    'cluster_id': 'cluster-1',
                    'dataset_key': 'analytics.storage',
                    'parameters': {'cluster_id': 'cluster-1'},
                }
            ],
            fallback_task_id='task-1',
        )

    assert result['succeeded'] == 0
    assert result['failed'] == 1
    assert stored == []
    assert len(failed) == 1
    dataset_key, persisted_error = failed[0]
    assert dataset_key == 'analytics.storage'
    assert '[analytics_dependency_unavailable]' in persisted_error
    assert 'Storage capability incomplete: PVC evidence is unavailable.' in persisted_error
    assert 'Recommended action:' in persisted_error

    failure = result['failures'][0]
    assert failure['code'] == 'analytics_dependency_unavailable'
    assert 'Storage Analysis for Primary could not satisfy its source dependency.' in failure['error']
    assert 'Storage capability incomplete: PVC evidence is unavailable.' in failure['error']
    assert failure['retryable'] == 'true'
    assert 'Review Integrations readiness' in failure['remediation']


def test_pending_page_context_preserves_forecast_htmx_replacement_id() -> None:
    app = Flask(__name__)
    app.add_url_rule(
        '/analytics/materialization/status',
        endpoint='analytics.materialization_status',
        view_func=lambda: '',
    )
    materialized = MaterializedRequest(
        result=SnapshotResult(None, None, 'missing', False),
        cluster=SimpleNamespace(id='cluster-1', name='Primary'),
        parameters={'cluster_id': 'cluster-1', 'history_window': '7d'},
        dispatched=True,
    )

    with app.test_request_context('/analytics/forecast?cluster_id=cluster-1&history_window=7d&forecast_horizon=180d'):
        context = pending_page_context(
            materialized=materialized,
            dataset_key='analytics.forecast',
            title='Capacity Forecast',
            description='Forecast history is prepared by the worker.',
            icon='chart-spline',
            page_id='forecast-page',
        )

    assert context['materialization_page_id'] == 'forecast-page'
    assert 'history_window=7d' in context['materialization_status_url']
    assert context['materialization_return_url'].startswith('/analytics/forecast?')
