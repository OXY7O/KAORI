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
    assert 'aria-label="Delete {{ row.cluster_name }}"' in registry
    assert 'h-9 w-9' in registry
    assert '<span class="sr-only">Delete</span>' in registry
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in registry
    assert 'data-delete-url=' in registry
    assert 'data-delete-name=' in registry
    assert 'row.cluster_name|tojson' not in registry
    assert "integrations/kubernetes/partials/_delete_modal.html" in template
    assert 'font-mono text-xs text-content-secondary' in registry
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
    assert "integrations/kubernetes/partials/_runtime_history.html" in template
    assert 'Kubernetes API Capability Detail' in capability
    assert 'Run Full Validation' in capability
    assert 'Delete Connection' in lifecycle
    assert "current_user.has_permission('clusters.manage')" in lifecycle
    assert 'kaori-integration-semantic' in template
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in lifecycle
    assert 'cluster.name|tojson' not in template


def test_kubernetes_runtime_history_uses_shared_expandable_detail_pattern():
    wrapper = _read('app/templates/integrations/kubernetes/partials/_runtime_history.html')
    shared = _read('app/templates/integrations/partials/_runtime_history.html')
    assert "integrations/partials/_runtime_history.html" in wrapper
    assert 'Recent Runtime Observations' in shared
    assert '<details id="{{ row.detail_id }}"' in shared
    assert 'View Detail' in shared
    assert 'Health Detail' in shared
    assert 'Diagnostic Evidence' in shared
    assert 'Kubernetes Version Lifecycle' in shared
    assert 'KAORI Current Band' in shared
    assert 'Accepted Compatibility Contract' in shared
    assert 'Selected Stable APIs' in shared
    assert 'pagination_ui.navigation_classes(disabled=false)' in shared
    assert 'pagination_ui.navigation_classes(disabled=true)' in shared


def test_legacy_cluster_registry_uses_safe_delete_trigger_and_csrf():
    page = _read('app/templates/cluster/index.html')
    table = _read('app/templates/cluster/partials/_table.html')
    modal = _read('app/templates/cluster/partials/_delete_modal.html')
    assert 'openDelete(url, name)' in page
    assert 'openDelete($el.dataset.deleteUrl, $el.dataset.deleteName)' in table
    assert "deleteName = '{{ cluster.name }}'" not in table
    assert 'name="csrf_token"' in modal
    assert 'x-bind:action="deleteUrl"' in modal
