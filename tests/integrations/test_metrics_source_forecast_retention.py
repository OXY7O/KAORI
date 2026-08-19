from __future__ import annotations

from types import SimpleNamespace

from app.integrations.observability.metrics_source.query_profiles import feature_contracts


class _QueryClient:
    def query(self, _expression: str) -> dict:
        return {
            'status': 'success',
            'data': {
                'result': [
                    {
                        'metric': {},
                        'value': [0, '1'],
                    }
                ]
            },
        }


def _forecast_contract():
    return next(item for item in feature_contracts.FEATURE_CONTRACTS if item.key == 'forecast.cpu')


def _definition(expression: str = 'vector(1)') -> SimpleNamespace:
    return SimpleNamespace(expression=expression, required_history='90d')


def test_forecast_contract_fails_when_90_day_history_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(feature_contracts, 'get_kubernetes_query', lambda _key: _definition())

    result = feature_contracts._evaluate(
        _QueryClient(),
        _forecast_contract(),
        sample_namespace='default',
        retention={
            '90d': {
                'available': False,
                'sample_time': '2026-05-21T00:00:00+00:00',
                'message': 'No historical samples found at the 90d horizon.',
            }
        },
    )

    assert result['status'] == 'failed'
    assert result['status_label'] == 'Failed'
    assert result['technical_checks'][-1]['label'] == '90d History Availability'
    assert result['technical_checks'][-1]['status'] == 'failed'
    assert 'at least 90d of queryable history' in result['recommendation']


def test_forecast_contract_is_ready_when_queries_and_90_day_history_are_ready(monkeypatch) -> None:
    monkeypatch.setattr(feature_contracts, 'get_kubernetes_query', lambda _key: _definition())

    result = feature_contracts._evaluate(
        _QueryClient(),
        _forecast_contract(),
        sample_namespace='default',
        retention={
            '90d': {
                'available': True,
                'sample_time': '2026-05-21T00:00:00+00:00',
                'message': 'Historical samples found at the 90d horizon.',
            }
        },
    )

    assert result['status'] == 'ready'
    assert result['status_label'] == 'Ready'
    assert result['technical_checks'][-1]['status'] == 'ready'
    assert 'Required history: Historical samples found at the 90d horizon.' in result['observed']
