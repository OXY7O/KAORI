from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_registry_pagination_is_htmx_and_disabled_navigation_is_not_a_link():
    registry = _read('app/templates/integrations/kubernetes/partials/_registry.html')
    routes = _read('app/integrations/routes.py')
    assert 'id="kubernetes-connection-registry"' in registry
    assert 'hx-target="#kubernetes-connection-registry"' in registry
    assert 'hx-push-url="true"' in registry
    assert "{% if pagination.has_prev %}" in registry
    assert "{% if pagination.has_next %}" in registry
    assert 'aria-disabled="true"' in registry
    assert '<span class="{{ pagination_ui.navigation_classes(disabled=true) }}" aria-disabled="true">' in registry
    assert 'pagination_ui.navigation_classes(disabled=true) }}" href=' not in registry
    assert "render_template('integrations/kubernetes/partials/_registry.html'" in routes


def test_kubernetes_detail_is_domain_workspace_with_delete_lifecycle():
    template = _read('app/templates/integrations/kubernetes/detail.html')
    capability = _read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
    lifecycle = _read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    for tab in (
        'Configuration',
        'Validation & Capabilities',
        'Runtime & History',
        'Inventory & Lifecycle',
    ):
        assert tab in template
    assert "integrations/kubernetes/partials/_connection_contract.html" in template
    assert "integrations/kubernetes/partials/_capability_workspace.html" in template
    assert "integrations/partials/_runtime_history.html" in template
    assert 'Kubernetes API Capability Detail' in capability
    assert 'Run Full Validation' in capability
    assert 'Delete Connection' in lifecycle
    assert "current_user.has_permission('clusters.manage')" in lifecycle
    assert 'kaori-integration-semantic' in template
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in lifecycle
    assert 'cluster.name|tojson' not in template


def test_kubernetes_runtime_history_uses_shared_expandable_detail_pattern():
    detail = _read('app/templates/integrations/kubernetes/detail.html')
    shared = _read('app/templates/integrations/partials/_runtime_history.html')
    assert "integrations/partials/_runtime_history.html" in detail
    assert not (ROOT / 'app/templates/integrations/kubernetes/partials/_runtime_history.html').exists()
    for fragment in (
        'Recent Runtime Observations',
        '<details id="{{ row.detail_id }}"',
        'View Detail',
        'Health Detail',
        'Diagnostic Evidence',
        'Kubernetes Version Lifecycle',
        'KAORI Current Band',
        'Accepted Compatibility Contract',
        'Selected Stable APIs',
        'pagination_ui.navigation_classes(disabled=false)',
        'pagination_ui.navigation_classes(disabled=true)',
    ):
        assert fragment in shared

