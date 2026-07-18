from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.prometheus.client import PrometheusClient
from app.prometheus.exceptions import PrometheusQueryError
from app.prometheus.query_profiles import audit as audit_module
from app.prometheus.query_profiles.audit import PromQLProfileAuditor, _unresolved_runtime_tokens
from app.prometheus.query_profiles.types import QueryDefinition


class FakeClient:
    def label_values(self, label):
        if label == '__name__':
            return {'status': 'success', 'data': ['metric_ok', 'metric_bad']}
        if label == 'namespace':
            return {'status': 'success', 'data': ['default']}
        return {'status': 'success', 'data': []}

    def series(self, metrics, **kwargs):
        return {'status': 'success', 'data': []}

    def query(self, expression):
        if expression == 'bad promql':
            raise PrometheusQueryError('HTTP 400: bad_data: parse error')
        return {'status': 'success', 'data': {'result': [{'metric': {}, 'value': [1, '1']}]}}

    def query_at(self, query, timestamp):
        return {'status': 'success', 'data': {'result': [{'metric': {}, 'value': [timestamp, '1']}]}}


@pytest.fixture
def definitions():
    return (
        QueryDefinition(key='test.ok', expression='count(metric_ok)', domain='app.analytics.capacity', required_metrics=('metric_ok',)),
        QueryDefinition(key='test.bad', expression='bad promql', domain='app.analytics.capacity', required_metrics=('metric_bad',)),
        QueryDefinition(key='test.deferred', expression='max_over_time(metric_ok[__TIME_RANGE__:__TIME_STEP__])', domain='app.analytics.capacity', required_metrics=('metric_ok',)),
    )


def test_profile_audit_isolates_rejected_and_runtime_bound_queries(monkeypatch, definitions):
    monkeypatch.setattr(audit_module, 'list_queries', lambda: definitions)
    monkeypatch.setattr(audit_module, 'evaluate_feature_contracts', lambda *args, **kwargs: [])

    result = PromQLProfileAuditor(FakeClient()).audit(execute_queries=True)
    by_key = {item['key']: item for item in result['results']}

    assert by_key['test.ok']['status'] == 'ready'
    assert by_key['test.bad']['status'] == 'blocked'
    assert 'parse error' in by_key['test.bad']['execution_error']
    assert by_key['test.bad']['executed_expression'] == 'bad promql'
    assert by_key['test.deferred']['status'] == 'deferred'
    assert result['blocked_count'] == 1
    assert result['deferred_count'] == 1


def test_runtime_placeholders_are_detected():
    assert _unresolved_runtime_tokens('max_over_time(metric[__TIME_RANGE__:__TIME_STEP__])') == (
        '__TIME_RANGE__',
        '__TIME_STEP__',
    )


@dataclass
class FakeResponse:
    status_code: int = 400
    text: str = ''

    def json(self):
        return {'status': 'error', 'errorType': 'bad_data', 'error': 'parse error at char 12'}


def test_client_error_contains_prometheus_error_detail():
    with pytest.raises(PrometheusQueryError, match='bad_data: parse error at char 12'):
        PrometheusClient._validate_response(FakeResponse())
