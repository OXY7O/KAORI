from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_protected_reveal_global_gate_is_explicit_without_bypassing_policy() -> None:
    service = read('app/kubernetes/operations/secrets/reveal_service.py')
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')

    clusters_block = service.split('def get_reveal_clusters(', 1)[1].split('def get_reveal_workspace(', 1)[0]
    assert 'if not _global_enabled():' in clusters_block
    assert 'return []' in clusters_block
    assert '_cluster_ready(cluster)' in clusters_block
    assert 'get_configured_enabled_namespace_names(cluster.id)' in clusters_block

    workspace_block = service.split('def get_reveal_workspace(', 1)[1].split('def _allowed_keys(', 1)[0]
    assert (
        'cluster_available = bool(_global_enabled() and cluster is not None and _cluster_ready(cluster))'
        in workspace_block
    )
    assert 'get_configured_enabled_namespace_names(normalized_cluster_id)' in workspace_block
    assert 'get_enabled_namespace_names(normalized_cluster_id)' in workspace_block

    assert 'KUBERNETES_SECRET_REVEAL_ENABLED=true' in page
    assert 'Protected Reveal globally disabled' in page
    assert 'selection is locked by the global kill switch' in page


def test_protected_reveal_reports_configured_policy_count_while_global_gate_is_off() -> None:
    service = read('app/kubernetes/operations/secrets/reveal_service.py')
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')

    assert 'SecretRevealNamespacePolicy' in service
    assert "SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))" in service
    assert "'configured_reveal_namespace_count': configured_reveal_namespace_count" in service
    assert 'configured_reveal_namespace_count' in page
    assert 'policy-enabled Namespace' in page


def test_secret_reveal_v16_layout_refinement_is_explicitly_superseded_by_v17() -> None:
    v16 = read('docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_6.md')
    v17 = read('docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_7.md')

    assert 'Side panels are symmetric at desktop breakpoints.' in v16
    assert 'Natural-height side panels' in v17
    assert 'Supersedes' in v17


def test_secret_reveal_v16_keeps_neutral_dark_mode_surfaces() -> None:
    protected = read('app/templates/kubernetes/operations/secrets/reveal.html')
    administration = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    for source in (protected, administration):
        assert 'bg-white' not in source
        assert 'bg-kaori-primary text-white' not in source or 'button type="submit"' in source
    assert 'bg-surface-card' in protected
    assert 'bg-surface-card' in administration
