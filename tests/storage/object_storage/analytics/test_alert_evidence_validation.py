from __future__ import annotations

import pytest

from app.storage.object_storage.analytics.alert_sources import _metrics_source_rows, build_alert_posture


@pytest.mark.parametrize(
    'payload',
    [
        {},
        {'status': 'error', 'data': {'result': []}},
        {'status': 'success'},
        {'status': 'success', 'data': {'result': None}},
        {'status': 'success', 'data': {'result': {}}},
        {'status': 'success', 'data': {'result': [{'metric': 'broken'}]}},
        {'status': 'success', 'data': {'result': [{'metric': {'alertname': 'A'}}]}},
        {
            'status': 'success',
            'data': {'result': [{'metric': {'alertname': 'A', 'alertstate': 'firing'}}]},
        },
    ],
)
def test_invalid_prometheus_alert_envelope_never_becomes_clean_empty(payload) -> None:
    with pytest.raises(ValueError):
        _metrics_source_rows(payload, source_label='Prometheus')


def test_confirmed_empty_metrics_alerts_are_distinct_from_unavailable_evidence() -> None:
    rows = _metrics_source_rows({'status': 'success', 'data': {'result': []}}, source_label='Prometheus')
    assert rows == []
    assert build_alert_posture({'connected': True, 'rows': rows})['status'] == 'No Active Alerts'
    assert build_alert_posture({'connected': False, 'rows': []})['status'] == 'Unknown'


def test_mixed_valid_invalid_metrics_alert_rows_fail_the_entire_collection() -> None:
    payload = {
        'status': 'success',
        'data': {
            'result': [
                {'metric': {'alertname': 'StorageFailure', 'alertstate': 'firing'}, 'value': [1, '1']},
                {'metric': 'invalid', 'value': [1, '1']},
            ]
        },
    }
    with pytest.raises(ValueError, match='malformed alert series'):
        _metrics_source_rows(payload, source_label='Prometheus')
