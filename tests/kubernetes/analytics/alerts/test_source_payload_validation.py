from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.analytics.alerts import sources


@pytest.fixture()
def cluster():
    return SimpleNamespace(id='cluster-alert-validation')


def test_alertmanager_valid_empty_list_is_a_real_success(monkeypatch, cluster) -> None:
    monkeypatch.setattr(
        sources,
        'get_alertmanager_alerts',
        lambda **_kwargs: {'connected': True, 'alerts': [], 'error': None},
    )
    monkeypatch.setattr(
        sources,
        'get_alertmanager_status',
        lambda **_kwargs: {'configured': True, 'label': 'Connected'},
    )
    alerts, status = sources.load_alertmanager_alerts(cluster=cluster)
    assert alerts == []
    assert status['connected'] is True
    assert status['error'] is None


@pytest.mark.parametrize(
    'invalid',
    [
        {'connected': True},
        {'connected': True, 'alerts': None},
        {'connected': True, 'alerts': {}},
        {'connected': True, 'alerts': [], 'error': 'query failed'},
        {'connected': True, 'alerts': [{'labels': {'alertname': 'Healthy'}}, 'bad item']},
        {'connected': True, 'alerts': [{'labels': {}}]},
        ['not a provider mapping'],
    ],
)
def test_alertmanager_malformed_payload_is_not_observed_zero(monkeypatch, cluster, invalid) -> None:
    monkeypatch.setattr(sources, 'get_alertmanager_alerts', lambda **_kwargs: invalid)
    monkeypatch.setattr(
        sources,
        'get_alertmanager_status',
        lambda **_kwargs: {'configured': True, 'label': 'Connected'},
    )
    alerts, status = sources.load_alertmanager_alerts(cluster=cluster)
    assert alerts == []
    assert status['connected'] is False
    assert status['resolved_source'] == 'none'
    assert status['error'] is not None


@pytest.fixture()
def metrics_query(monkeypatch):
    query = SimpleNamespace(response={})
    monkeypatch.setattr(sources, 'resolve_instance_for_cluster', lambda _id: object())
    monkeypatch.setattr(
        sources,
        'MetricsService',
        lambda _cluster: SimpleNamespace(instant_query=lambda _promql: query.response),
    )
    return query


def test_metrics_source_valid_empty_vector_is_success(cluster, metrics_query) -> None:
    metrics_query.response = {
        'status': 'success',
        'data': {'resultType': 'vector', 'result': []},
    }
    alerts, status = sources.load_metrics_source_alerts(cluster=cluster)
    assert alerts == []
    assert status['connected'] is True


@pytest.mark.parametrize(
    'invalid',
    [
        {},
        {'status': 'error', 'data': {'result': []}},
        {'data': {}},
        {'data': {'result': None}},
        {'data': {'result': {}}},
        {'data': {'resultType': 'matrix', 'result': []}},
        {'data': {'result': [{'metric': {'alertname': 'A'}}]}},
        {'data': {'result': [{'metric': {'alertname': 'A'}, 'value': [0, '1']}, {'metric': None}]}},
    ],
)
def test_metrics_source_malformed_payload_is_not_observed_zero(cluster, metrics_query, invalid) -> None:
    metrics_query.response = invalid
    alerts, status = sources.load_metrics_source_alerts(cluster=cluster)
    assert alerts == []
    assert status['connected'] is False
    assert status['resolved_source'] == 'none'
    assert status['error'] is not None


def test_malformed_alertmanager_triggers_existing_metrics_fallback(monkeypatch, cluster, metrics_query) -> None:
    monkeypatch.setattr(
        sources,
        'get_alertmanager_alerts',
        lambda **_kwargs: {'connected': True, 'alerts': 'not an alert list'},
    )
    metrics_query.response = {'data': {'result': []}}
    alerts, status = sources.load_alerts_by_source(cluster=cluster, source='auto')
    assert alerts == []
    assert status['connected'] is True
    assert status['resolved_source'] == 'metrics_source'
    assert status['fallback_used'] is True
    assert status['selected_source'] == 'auto'


def test_both_sources_malformed_report_unknown_not_connected(monkeypatch, cluster, metrics_query) -> None:
    monkeypatch.setattr(sources, 'get_alertmanager_alerts', lambda **_kwargs: {'connected': True})
    metrics_query.response = {'data': {'result': None}}
    alerts, status = sources.load_alerts_by_source(cluster=cluster, source='auto')
    assert alerts == []
    assert status['connected'] is False
    assert status['resolved_source'] == 'none'
    assert status['error'] is not None
