from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_landing_uses_semantic_workspace_and_delete_modal():
    template = _read('app/templates/integrations/kubernetes.html')
    assert 'kaori-integration-semantic' in template
    assert 'Kubernetes Connection Registry' in template
    assert "cluster.delete_cluster_route" in template
    assert 'Delete</button>' in template
    assert "integrations/kubernetes/partials/_delete_modal.html" in template
    assert 'font-mono' not in template
    assert 'border-emerald-' not in template


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


def test_kubernetes_runtime_history_uses_standard_table():
    template = _read('app/templates/integrations/kubernetes/partials/_runtime_history.html')
    assert 'Recent Runtime Observations' in template
    assert '<table' in template
    assert 'rounded-xl' in template
    assert 'rounded-2xl' not in template
