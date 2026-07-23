from types import SimpleNamespace

from app.prometheus import consumer as consumer_module


class _Client:
    def __init__(self, instance_id: int) -> None:
        self.instance_id = instance_id

    def query(self, promql: str):
        return {'instance_id': self.instance_id, 'query': promql}

    def query_range(self, promql: str, start: str, end: str, step: str):
        return {
            'instance_id': self.instance_id,
            'query': promql,
            'start': start,
            'end': end,
            'step': step,
        }


class _Registry:
    def execute(self, operation, instance, **kwargs):
        assert operation == 'client.build'
        return _Client(instance.id)


def _candidate(instance_id: int):
    instance = SimpleNamespace(
        id=instance_id,
        name=f'prometheus-{instance_id}',
        endpoint='https://prometheus.example',
        readiness_status='ready',
        validation_message=None,
        last_status='connected',
        last_error=None,
        last_checked_at=None,
        last_response_time_ms=10,
        endpoint_product='prometheus',
        compatibility_profile='prometheus-v2',
        capability_profile='kubernetes-v1',
        capabilities={'available': ['instant_query', 'range_query']},
    )
    binding = SimpleNamespace(selector_json={'matchers': []})
    return SimpleNamespace(instance=instance, binding=binding, decision_reason='ready')


def test_range_query_re_resolves_for_range_capability(monkeypatch) -> None:
    default = _candidate(1)
    range_source = _candidate(2)
    requested = []

    def resolve(**kwargs):
        required = tuple(kwargs.get('required_technical_capabilities') or ())
        requested.append(required)
        selected = range_source if required == ('range_query',) else default
        return SimpleNamespace(selected=selected, candidates=(selected,))

    monkeypatch.setattr(consumer_module, 'resolve_prometheus_sources', resolve)
    monkeypatch.setattr(consumer_module, 'get_integration', lambda provider: _Registry())

    consumer = consumer_module.PrometheusConsumer(SimpleNamespace(id='cluster-1', name='Production'))
    result = consumer.execute_range_query('up', '1', '2', '30s')

    assert result.ok is True
    assert result.payload['instance_id'] == 2
    assert result.source.instance_id == 2
    assert result.source.fallback_used is True
    assert requested == [(), ('range_query',)]


def test_operation_fails_closed_when_no_source_has_capability(monkeypatch) -> None:
    default = _candidate(1)

    def resolve(**kwargs):
        required = tuple(kwargs.get('required_technical_capabilities') or ())
        if required:
            blocked = SimpleNamespace(decision_reason='Missing validated technical capabilities: range_query.')
            return SimpleNamespace(selected=None, candidates=(blocked,))
        return SimpleNamespace(selected=default, candidates=(default,))

    monkeypatch.setattr(consumer_module, 'resolve_prometheus_sources', resolve)
    monkeypatch.setattr(consumer_module, 'get_integration', lambda provider: _Registry())

    consumer = consumer_module.PrometheusConsumer(SimpleNamespace(id='cluster-1', name='Production'))
    result = consumer.execute_range_query('up', '1', '2', '30s')

    assert result.ok is False
    assert result.diagnostics[0].code == 'provider_query_failed'
    assert 'range_query' in (result.diagnostics[0].detail or '')
