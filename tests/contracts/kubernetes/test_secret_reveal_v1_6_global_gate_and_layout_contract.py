from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_protected_reveal_global_gate_is_explicit_without_bypassing_policy() -> None:
    service = read('app/kubernetes_operations/secrets/reveal_service.py')
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')

    clusters_block = service.split('def get_reveal_clusters(', 1)[1].split('def get_reveal_workspace(', 1)[0]
    assert 'if not _global_enabled():' in clusters_block
    assert 'return []' in clusters_block
    assert '_cluster_ready(cluster)' in clusters_block
    assert 'get_configured_enabled_namespace_names(cluster.id)' in clusters_block

    workspace_block = service.split('def get_reveal_workspace(', 1)[1].split('def _allowed_keys(', 1)[0]
    assert 'cluster_available = bool(_global_enabled() and cluster is not None and _cluster_ready(cluster))' in workspace_block
    assert 'get_configured_enabled_namespace_names(normalized_cluster_id)' in workspace_block
    assert 'get_enabled_namespace_names(normalized_cluster_id)' in workspace_block

    assert 'KUBERNETES_SECRET_REVEAL_ENABLED=true' in page
    assert 'Protected Reveal globally disabled' in page
    assert 'selection is locked by the global kill switch' in page


def test_protected_reveal_reports_configured_policy_count_while_global_gate_is_off() -> None:
    service = read('app/kubernetes_operations/secrets/reveal_service.py')
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')

    assert 'SecretRevealNamespacePolicy' in service
    assert "SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))" in service
    assert "'configured_reveal_namespace_count': configured_reveal_namespace_count" in service
    assert 'configured_reveal_namespace_count' in page
    assert 'policy-enabled Namespace' in page


def test_secret_reveal_side_panels_use_explicit_stretch_geometry() -> None:
    context_rail = read('app/templates/components/context_rail.html')
    protected = read('app/templates/kubernetes_operations/secrets/reveal.html')
    administration = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    assert "layout_classes(width='default', align='start')" in context_rail
    assert "'xl:items-stretch' if align == 'stretch' else 'xl:items-start'" in context_rail
    assert 'rail_classes(fill=false)' in context_rail
    assert "'h-full' if fill else ''" in context_rail

    assert "context_rail.layout_classes('wide', 'stretch')" in protected
    assert 'context_rail.rail_classes(true)' in protected
    assert "extra_classes='h-full'" in protected
    assert 'Protected one-time reveal lifecycle.' in protected

    assert 'grid items-stretch gap-4' in administration
    assert 'h-full overflow-hidden rounded-2xl' in administration
    assert 'flex h-full flex-col overflow-hidden rounded-2xl' in administration
    assert 'grid flex-1 gap-3' in administration


def test_secret_reveal_v16_keeps_neutral_dark_mode_surfaces() -> None:
    protected = read('app/templates/kubernetes_operations/secrets/reveal.html')
    administration = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    for source in (protected, administration):
        assert 'bg-white' not in source
        assert 'bg-kaori-primary text-white' not in source or 'button type="submit"' in source
    assert 'bg-surface-card' in protected
    assert 'bg-surface-card' in administration
