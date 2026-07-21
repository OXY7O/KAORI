from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_binding_contract_declares_complete_prometheus_consumer_scope():
    source = (ROOT / 'app/prometheus/binding_contract.py').read_text()

    for capability in (
        'metrics',
        'capacity',
        'utilization',
        'storage',
        'workload',
        'forecast',
        'top_consumers',
        'alert_metrics',
    ):
        assert repr(capability) in source
    assert 'effective_prometheus_binding_capabilities' in source
    assert 'normalize_prometheus_binding_capabilities' in source


def test_resolver_uses_effective_binding_contract_and_assessment_evidence():
    resolver = (ROOT / 'app/prometheus/resolver.py').read_text()

    assert 'effective_prometheus_binding_capabilities(item.binding)' in resolver
    assert "capability_payload.get('assessments')" in resolver
    assert "in {'available', 'ready'}" in resolver


def test_full_binding_validation_persists_legacy_scope_repair():
    service = (ROOT / 'app/prometheus/service.py').read_text()

    assert 'normalize_prometheus_binding_capabilities(binding)' in service
    assert 'capability_scope=list(PROMETHEUS_BINDING_CAPABILITIES)' in service


def test_resolution_card_exposes_primary_blocker_without_expansion():
    template = (
        ROOT
        / 'app/templates/prometheus/partials/_detail_scope.html'
    ).read_text()
    presentation = (ROOT / 'app/prometheus/presentation.py').read_text()

    assert 'consumer.primary_blocker' in template
    assert "'primary_blocker':" in presentation
