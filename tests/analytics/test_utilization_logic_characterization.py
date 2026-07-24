from __future__ import annotations

from app.analytics.utilization.service import UtilizationService, _empty_utilization_snapshot, _safe_float


def test_utilization_prometheus_scalar_and_series_parsing_fails_closed() -> None:
    assert UtilizationService._extract_scalar({'data': {'result': [{'value': [1, '42.5']}]}}) == 42.5
    assert UtilizationService._extract_scalar({'data': {'result': []}}) == 0.0
    assert UtilizationService._extract_scalar({'invalid': True}) == 0.0

    assert UtilizationService._extract_series({'data': {'result': [{'values': [[1, '10.5'], [2, '11.5']]}]}}) == [
        {'timestamp': 1.0, 'value': 10.5},
        {'timestamp': 2.0, 'value': 11.5},
    ]
    assert UtilizationService._extract_series({'data': {'result': []}}) == []


def test_utilization_consumer_normalization_preserves_identity() -> None:
    consumers = UtilizationService._extract_consumers(
        {
            'data': {
                'result': [
                    {
                        'metric': {'namespace': 'payments', 'pod': 'api-1'},
                        'value': [1, '3.5'],
                    },
                    {
                        'metric': {},
                        'value': [1, 'invalid'],
                    },
                ]
            }
        }
    )

    assert consumers == [
        {'namespace': 'payments', 'pod': 'api-1', 'value': 3.5},
        {'namespace': '-', 'pod': '-', 'value': 0.0},
    ]
    assert UtilizationService._escape_label_value('node\\"a') == 'node\\\\\\"a'


def test_utilization_snapshot_numeric_contract_is_stable() -> None:
    assert _safe_float('12.345') == 12.35
    assert _safe_float('invalid') == 0.0
    assert _empty_utilization_snapshot() == {
        'cpu_percent': 0.0,
        'memory_percent': 0.0,
        'storage_percent': 0.0,
        'pod_percent': 0.0,
    }
