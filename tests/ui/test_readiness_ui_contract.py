from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_registry_separates_api_and_operational_coverage():
    template = read('app/templates/integrations/kubernetes/partials/_registry.html')
    assert 'Kubernetes API' in template
    assert 'Operational Coverage' in template
    assert '>Inventory<' in template
    assert '>Analytics<' in template
    assert '>Alerts<' in template


def test_provider_binding_actions_explain_revalidation():
    for path in (
        'app/templates/prometheus/partials/_detail_scope.html',
        'app/templates/alertmanager/partials/_detail_scope.html',
    ):
        template = read(path)
        assert 'Validate Binding' in template
        assert 'Revalidate Binding' in template
        assert "integrations/partials/_binding_readiness.html" in template


def test_shared_binding_posture_explains_three_statuses():
    template = read('app/templates/integrations/partials/_binding_readiness.html')
    assert 'Source Readiness' in template
    assert 'Binding Validation' in template
    assert 'Operational Status' in template
