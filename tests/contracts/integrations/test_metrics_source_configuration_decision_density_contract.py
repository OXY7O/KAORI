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


def test_metrics_source_configuration_exposes_provider_and_consumer_boundary() -> None:
    template = read('app/templates/integrations/observability/metrics_source/partials/_detail_configuration.html')
    assert 'provider_configuration_contract.render(' in template
    assert "metrics_source_label ~ ' Metrics Endpoint'" in template
    assert 'metrics_source_label ~ " Query API"' in template
    assert 'Metrics Authority' in template
    assert 'bindings only govern consumer selection' in template
    assert 'url_for("metrics.edit_instance"' in template
