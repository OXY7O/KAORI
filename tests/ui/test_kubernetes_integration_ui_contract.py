from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_landing_uses_semantic_workspace_and_delete_modal():
    template = _read('app/templates/integrations/kubernetes.html')
    registry = _read('app/templates/integrations/kubernetes/partials/_registry.html')
    assert 'kaori-integration-semantic' in template
    assert 'Kubernetes Integration Overview' in template
    assert template.index('Kubernetes Integration Overview') < template.index("integrations/kubernetes/partials/_registry.html")
    assert 'Registered Connections' in template
    assert 'Validated Connections' in template
    assert 'Needs Attention' in template
    assert 'Scope Bindings' in template
    assert 'rounded-2xl border border-outline-default bg-surface-card shadow-sm' in template
    assert 'grid gap-4 lg:grid-cols-3' not in template
    assert 'Kubernetes Connection Registry' in registry
    assert "cluster.delete_cluster_route" in registry
    assert 'Delete</button>' in registry
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in registry
    assert 'data-delete-url=' in registry
    assert 'data-delete-name=' in registry
    assert 'row.cluster_name|tojson' not in registry
    assert "integrations/kubernetes/partials/_delete_modal.html" in template
    assert 'font-mono' not in template + registry
    assert 'border-emerald-' not in template + registry


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
    for tab in (
        'Connection & Contract',
        'Compatibility & Capabilities',
        'Runtime & History',
        'Inventory & Lifecycle',
    ):
        assert tab in template
    assert 'API Compatibility & Capability Matrix' in template
    assert 'Delete Connection' in template
    assert "current_user.has_permission('clusters.manage')" in template
    assert 'kaori-integration-semantic' in template
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in template
    assert 'cluster.name|tojson' not in template


def test_kubernetes_runtime_history_uses_standard_table():
    template = _read('app/templates/integrations/kubernetes/partials/_runtime_history.html')
    assert 'Recent Runtime Observations' in template
    assert '<table' in template
    assert 'rounded-xl' in template
    assert 'rounded-2xl' not in template


def test_legacy_cluster_registry_uses_safe_delete_trigger_and_csrf():
    page = _read('app/templates/cluster/index.html')
    table = _read('app/templates/cluster/partials/_table.html')
    modal = _read('app/templates/cluster/partials/_delete_modal.html')
    assert 'openDelete(url, name)' in page
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in table
    assert "deleteName = '{{ cluster.name }}'" not in table
    assert 'name="csrf_token"' in modal
    assert 'x-bind:action="deleteUrl"' in modal
