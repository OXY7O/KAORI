from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_expandable_detail_contract_exists():
    macro = (ROOT / 'app/templates/components/details/_expandable_row.html').read_text()
    script = (ROOT / 'app/static/js/detail_rows.js').read_text()
    assert 'data-detail-toggle' in macro
    assert 'data-detail-content' in macro
    assert 'Hide Details' in script
    assert 'closeGroup' in script


def test_kubernetes_registry_uses_htmx_detail_partial():
    registry = (ROOT / 'app/templates/integrations/kubernetes/partials/_registry.html').read_text()
    assert 'expandable.toggle_button' in registry
    assert 'kubernetes_registry_details' in registry
    assert 'x-show="expanded"' not in registry
    assert 'Kubernetes Connection Details' not in registry


def test_kubernetes_registry_detail_route_is_provider_local():
    routes = (ROOT / 'app/integrations/routes.py').read_text()
    assert "/kubernetes/<string:cluster_id>/registry-details" in routes
    assert 'build_kubernetes_registry_row(cluster_id)' in routes
