from __future__ import annotations

from types import SimpleNamespace

from app.integrations.registry import observability


class _Query:
    def __init__(self, rows, hits):
        self.rows = rows
        self.hits = hits

    def join(self, *_args):
        return self

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def all(self):
        self.hits.append('read')
        return self.rows


def test_batched_metrics_source_readiness_has_constant_query_count(monkeypatch) -> None:
    from app.models.integration import IntegrationBinding
    from app.models.metrics_source import MetricsSource

    binding_hits: list[str] = []
    source_hits: list[str] = []
    bindings = [
        SimpleNamespace(asset_key='1', integration_instance_id=9, enabled=True),
        SimpleNamespace(asset_key='2', integration_instance_id=9, enabled=True),
    ]
    source = SimpleNamespace(integration_instance_id=9)
    monkeypatch.setattr(IntegrationBinding, 'query', _Query(bindings, binding_hits))
    monkeypatch.setattr(MetricsSource, 'query', _Query([source], source_hits))
    monkeypatch.setattr(
        observability,
        '_evaluate_binding',
        lambda binding, _source, **_kw: SimpleNamespace(eligible=binding.asset_key == '1'),
    )
    fleet = [SimpleNamespace(id=i) for i in range(1, 101)]
    assert observability.registry_metrics_ready_provider_ids(fleet) == {1}
    assert binding_hits == ['read']
    assert source_hits == ['read']


def test_empty_fleet_does_not_query_metrics_binding_registry(monkeypatch) -> None:
    from app.models.integration import IntegrationBinding

    monkeypatch.setattr(
        IntegrationBinding,
        'query',
        _Query([], []),
    )
    assert observability.registry_metrics_ready_provider_ids([]) == set()
