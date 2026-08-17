from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_provider_configuration_contract_is_compact_and_read_only() -> None:
    shared = read('app/templates/integrations/components/_provider_configuration_contract.html')
    assert 'Connection Contract' in shared
    assert 'Connection Evidence' in shared
    assert 'Operational Context' in read('app/templates/integrations/components/_provider_operational_context.html')
    operational = read('app/templates/integrations/components/_provider_operational_context.html')
    assert 'Step {{ loop.index }}' in operational
    assert 'Configure Connection' in shared
    assert '<form' not in shared


def test_prometheus_configuration_exposes_provider_and_consumer_boundary() -> None:
    prometheus = read('app/templates/prometheus/partials/_detail_configuration.html')
    assert 'provider_configuration_contract.render(' in prometheus
    assert 'Prometheus API Endpoint' in prometheus
    assert 'Thanos Query API Endpoint' in prometheus
    assert 'metrics_source_label ~ " owns its metrics and retention.' in prometheus
    assert 'source readiness separate from consumer bindings and query routing' in prometheus
    assert 'url_for("prometheus.edit_instance"' in prometheus
