"""Expected Metrics Source context errors fail closed without hiding programming defects."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.kubernetes.analytics.capacity import service as capacity_module
from app.kubernetes.analytics.common import context as context_module
from app.kubernetes.analytics.utilization import materialization as utilization_module
from app.kubernetes.analytics.workload import service as workload_module


def _raise(error: Exception) -> Callable[..., None]:
    def throw(*_args: object, **_kwargs: object) -> None:
        raise error

    return throw


def _blocker(_cluster: object, **_kwargs: object) -> dict[str, str]:
    return {'kind': 'metrics_source_connection'}


def _cluster() -> SimpleNamespace:
    return SimpleNamespace(id=17, name='Review Cluster')


def _stub_cluster(monkeypatch: pytest.MonkeyPatch, module: Any) -> SimpleNamespace:
    cluster = _cluster()
    query = SimpleNamespace(order_by=lambda *_args: SimpleNamespace(all=lambda: [cluster]))
    monkeypatch.setattr(module.Cluster, 'query', query)
    monkeypatch.setattr(module, 'get_selected_cluster', lambda **_kwargs: cluster)
    monkeypatch.setattr(
        module, 'resolve_instance_for_cluster', lambda _cluster_id: SimpleNamespace(endpoint='https://metrics.test')
    )
    monkeypatch.setattr(module, 'metrics_source_connection_blocker', _blocker)
    return cluster


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('SQL unavailable'),
        RuntimeError('missing context'),
        TypeError('invalid type'),
        ValueError('bad value'),
    ],
)
@pytest.mark.parametrize('view', ['summary', 'trend', 'node'])
def test_expected_utilization_query_failure_remains_blocked(
    monkeypatch: pytest.MonkeyPatch, error: Exception, view: str
) -> None:
    service = SimpleNamespace(
        get_metrics_source_status=_raise(error),
        get_worker_node_names=_raise(error),
        get_node_names=_raise(error),
    )
    monkeypatch.setattr(
        utilization_module,
        '_dependency_context',
        lambda _args: (_cluster(), service, {'dependency_blocker': None}),
    )
    monkeypatch.setattr(utilization_module, '_recommendation_context', lambda *_args: {})
    monkeypatch.setattr(utilization_module, 'metrics_source_connection_blocker', _blocker)
    views = {
        'summary': utilization_module.get_utilization_summary_context,
        'trend': utilization_module.get_utilization_trend_context,
        'node': utilization_module.get_utilization_node_context,
    }

    with Flask(__name__).app_context():
        result = views[view]({})

    assert result['dependency_blocker']['kind'] == 'metrics_source_connection'


@pytest.mark.parametrize('view', ['summary', 'trend', 'node'])
def test_unexpected_utilization_programming_defect_propagates(monkeypatch: pytest.MonkeyPatch, view: str) -> None:
    error = LookupError('unexpected defect')
    service = SimpleNamespace(
        get_metrics_source_status=_raise(error),
        get_worker_node_names=_raise(error),
        get_node_names=_raise(error),
    )
    monkeypatch.setattr(
        utilization_module,
        '_dependency_context',
        lambda _args: (_cluster(), service, {'dependency_blocker': None}),
    )
    monkeypatch.setattr(utilization_module, '_recommendation_context', lambda *_args: {})
    views = {
        'summary': utilization_module.get_utilization_summary_context,
        'trend': utilization_module.get_utilization_trend_context,
        'node': utilization_module.get_utilization_node_context,
    }

    with pytest.raises(LookupError, match='unexpected defect'):
        views[view]({})


@pytest.mark.parametrize('mode', ['review', 'connected', 'health'])
@pytest.mark.parametrize('error', [SQLAlchemyError('db down'), RuntimeError('context absent'), ValueError('bad state')])
def test_expected_shared_metrics_context_failure_blocks_source(
    monkeypatch: pytest.MonkeyPatch, mode: str, error: Exception
) -> None:
    _stub_cluster(monkeypatch, context_module)
    monkeypatch.setattr(
        context_module,
        'resolve_metrics_sources',
        lambda **_kwargs: SimpleNamespace(selected=SimpleNamespace(operational_state='ready')),
    )
    if mode == 'health':
        monkeypatch.setattr(context_module, 'MetricsService', lambda _cluster: object())
        monkeypatch.setattr(
            context_module,
            'UtilizationService',
            lambda _source: SimpleNamespace(get_metrics_source_status=_raise(error)),
        )
    else:
        monkeypatch.setattr(context_module, 'MetricsService', _raise(error))

    with Flask(__name__).app_context():
        _clusters, _cluster_value, service, result = context_module.build_analysis_utilization_context(
            {}, check_metrics_source_connection=mode != 'review'
        )

    assert service is None
    assert result['dependency_blocker']['kind'] == 'metrics_source_connection'


@pytest.mark.parametrize('mode', ['review', 'connected', 'health'])
def test_unexpected_shared_metrics_context_defect_propagates(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    _stub_cluster(monkeypatch, context_module)
    monkeypatch.setattr(
        context_module,
        'resolve_metrics_sources',
        lambda **_kwargs: SimpleNamespace(selected=SimpleNamespace(operational_state='ready')),
    )
    if mode == 'health':
        monkeypatch.setattr(context_module, 'MetricsService', lambda _cluster: object())
        monkeypatch.setattr(
            context_module,
            'UtilizationService',
            lambda _source: SimpleNamespace(get_metrics_source_status=_raise(LookupError('unexpected defect'))),
        )
    else:
        monkeypatch.setattr(context_module, 'MetricsService', _raise(LookupError('unexpected defect')))

    with Flask(__name__).app_context():
        with pytest.raises(LookupError, match='unexpected defect'):
            context_module.build_analysis_utilization_context({}, check_metrics_source_connection=mode != 'review')


@pytest.mark.parametrize(
    'error', [SQLAlchemyError('db down'), RuntimeError('context absent'), ValueError('bad source')]
)
def test_expected_workload_status_error_keeps_empty_payload(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    monkeypatch.setattr(
        workload_module,
        'build_analysis_utilization_context',
        lambda **_kwargs: ([], _cluster(), object(), {}),
    )
    monkeypatch.setattr(workload_module, '_empty_materialized_context', lambda _range: {})
    monkeypatch.setattr(workload_module, 'get_empty_workload_payload', lambda *_args: {'rows': []})
    monkeypatch.setattr(workload_module, 'metrics_source_connection_blocker', _blocker)
    monkeypatch.setattr(
        workload_module,
        'WorkloadAnalysisService',
        lambda _util: SimpleNamespace(
            requirements=lambda: SimpleNamespace(ok=True), get_metrics_source_status=_raise(error)
        ),
    )

    result = workload_module.get_workload_analysis_context({})

    assert result['dependency_blocker']['kind'] == 'metrics_source_connection'
    assert result['rows'] == []


def test_unexpected_workload_status_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workload_module,
        'build_analysis_utilization_context',
        lambda **_kwargs: ([], _cluster(), object(), {}),
    )
    monkeypatch.setattr(workload_module, '_empty_materialized_context', lambda _range: {})
    monkeypatch.setattr(
        workload_module,
        'WorkloadAnalysisService',
        lambda _util: SimpleNamespace(
            requirements=lambda: SimpleNamespace(ok=True),
            get_metrics_source_status=_raise(LookupError('unexpected defect')),
        ),
    )

    with pytest.raises(LookupError, match='unexpected defect'):
        workload_module.get_workload_analysis_context({})


@pytest.mark.parametrize(
    'error', [SQLAlchemyError('db down'), RuntimeError('context absent'), ValueError('bad source')]
)
def test_expected_capacity_source_failure_keeps_blocked_status(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    _stub_cluster(monkeypatch, capacity_module)
    monkeypatch.setattr(capacity_module, 'get_empty_capacity_payload', lambda **_kwargs: {})
    monkeypatch.setattr(capacity_module, 'MetricsService', _raise(error))

    with Flask(__name__).app_context():
        result = capacity_module.get_capacity_page_context({})

    assert result['dependency_blocker']['kind'] == 'metrics_source_connection'


def test_unexpected_capacity_source_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_cluster(monkeypatch, capacity_module)
    monkeypatch.setattr(capacity_module, 'get_empty_capacity_payload', lambda **_kwargs: {})
    monkeypatch.setattr(capacity_module, 'MetricsService', _raise(LookupError('unexpected defect')))

    with Flask(__name__).app_context():
        with pytest.raises(LookupError, match='unexpected defect'):
            capacity_module.get_capacity_page_context({})
