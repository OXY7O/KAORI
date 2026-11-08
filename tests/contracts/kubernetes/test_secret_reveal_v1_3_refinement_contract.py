from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_secret_reveal_readiness_exposes_cluster_credential() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')
    service = read('app/platform_operations/kubernetes/secret_reveal/service.py')
    template = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    assert 'def cluster_reveal_readiness_evidence(' in policy
    assert "'credential_configured': credential_configured" in policy
    assert "'selected_cluster_readiness': selected_cluster_readiness" in service
    assert 'Cluster Credential' in template
    assert 'selected_cluster_readiness.credential_configured' in template
    assert 'Review credential availability and attest to the two security prerequisites for this cluster.' in template
    assert 'Encryption at Rest' in template
    assert 'Metadata Audit' in template


def test_secret_reveal_namespace_source_is_snapshot_backed_and_tri_state() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')
    service = read('app/platform_operations/kubernetes/secret_reveal/service.py')
    section = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html')
    table = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert 'class NamespaceSourceSnapshot:' in policy
    assert 'def get_namespace_source_snapshot(' in policy
    assert "state='unavailable'" in policy
    assert "live_state = 'unknown'" in policy
    assert "row['live_state'] == 'missing'" in service
    assert "row['live_state'] == 'unknown'" in service
    assert 'Live Namespace Source Unavailable' in section
    assert 'Live Namespace' in table
    assert "live_label = 'Available'" in table
    assert "else 'Unknown'" in table


def test_secret_reveal_filtering_does_not_request_live_refresh() -> None:
    platform_routes = read('app/platform_operations/kubernetes/routes.py')
    reveal_routes = read('app/platform_operations/kubernetes/secret_reveal/routes.py')
    section = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html')

    assert "refresh_namespace='1'" in platform_routes
    assert "refresh_namespace_source=request.args.get('refresh_namespace') == '1'" in reveal_routes
    assert 'refresh_namespace=1' in section
    filter_form = section.split('hx-trigger=', 1)[1].split('</form>', 1)[0]
    assert 'refresh_namespace' not in filter_form


def test_secret_reveal_policy_mutation_keeps_fresh_live_guardrail() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')
    table = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert 'verify_live_namespace(cluster, normalized_namespace)' in policy
    assert "value != 'disabled' and (not selected_cluster_ready or row.live_state != 'available')" in table
    assert ':disabled="current === initial"' in table
    assert 'x-model="current"' in table
    assert 'class="{{ table_ui.action_classes() }}"' in table
    assert 'Edit Policy' in table
    assert 'Save Policy' in table


def test_secret_reveal_clear_surfaces_and_oob_posture_are_locked() -> None:
    workspace = read('app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html')
    cluster = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    assert 'Configured prerequisites and policies do not prove live access.' in workspace
    assert '{% include "platform_operations/kubernetes/secret_reveal/_cluster_workspace.html" %}' in workspace
    assert 'Activation Boundary' in cluster
    assert 'Kubernetes Boundary' in cluster
    assert 'Least-privilege Kubernetes RBAC remains the final authorization boundary.' in cluster
    assert 'secret-reveal-protected-cluster-count' in workspace
    assert 'secret-reveal-enabled-namespace-count' in workspace
    assert 'secret-reveal-selected-cluster-posture' in workspace
    assert 'hx-swap-oob="outerHTML"' in cluster
    assert 'class="min-w-0 overflow-hidden rounded-xl border border-outline-subtle"' in cluster
    assert '<aside class="overflow-hidden rounded-2xl border border-kaori-primary bg-kaori-primary' not in cluster
    assert 'Policies activate only when cluster readiness is satisfied.' in cluster
