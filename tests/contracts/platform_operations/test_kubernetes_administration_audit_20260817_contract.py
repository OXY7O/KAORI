import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_jinja_assignment(source: str, variable: str, value: str) -> bool:
    pattern = r'{%\s*set\s+' + re.escape(variable) + r"\s*=\s*([\"'])" + re.escape(value) + r'\1\s*%}'
    return re.search(pattern, source) is not None


def test_kubernetes_administration_posture_is_factual_not_hardcoded_available() -> None:
    presentation = read('app/platform_operations/kubernetes/presentation.py')
    page = read('app/templates/platform_operations/kubernetes/index.html')
    overview = read('app/templates/platform_operations/kubernetes/_overview_workspace.html')

    assert 'def _administration_posture(' in presentation
    for label in (
        'Setup Required',
        'Global Gate Disabled',
        'Readiness Review',
        'Partial Readiness',
        'Policy Required',
        'Operational',
    ):
        assert label in presentation
    assert "'administration_status_label': status_label" in presentation
    assert "'administration_status_tone': status_tone" in presentation
    assert "'administration_status_detail': status_detail" in presentation

    assert 'Control Status: Protected Secret Reveal Available' not in page
    assert 'Available Controls' not in page
    assert 'Managed Controls' in page
    assert 'administration_status_label' in page
    assert 'administration_status_tone' in page
    assert 'administration_status_detail' in overview
    assert "table_label.status_label('Available', 'normal')" not in overview
    assert "table_label.status_label('1 Available Control', 'info')" not in overview
    assert "table_label.status_label('1 Managed Control', 'info')" in overview
    assert "administration_status_tone == 'normal'" in overview


def test_secret_reveal_readiness_fails_closed_when_canonical_connection_is_missing() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')

    readiness = policy.split('def cluster_reveal_readiness_evidence(', 1)[1].split('def cluster_reveal_readiness(', 1)[
        0
    ]
    assert 'try:' in readiness
    assert 'credential_configured = bool(kubeconfig_for_cluster(cluster))' in readiness
    assert 'except (RuntimeError, ValueError):' in readiness
    assert 'credential_configured = False' in readiness


def test_kubernetes_administration_no_cluster_and_namespace_states_are_canonical() -> None:
    cluster = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    namespace = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert has_jinja_assignment(cluster, 'empty_state_title', 'No Kubernetes Cluster Registered')
    assert has_jinja_assignment(cluster, 'empty_state_permission', 'clusters.manage')
    assert 'empty_state_show_admin_required = true' in cluster
    assert 'p-8 text-center' not in cluster

    assert has_jinja_assignment(namespace, 'empty_state_title', 'No Namespace Matches the Current Filters')
    assert has_jinja_assignment(namespace, 'blocked_state_title', 'Live Namespace Source Unavailable')
    assert has_jinja_assignment(namespace, 'empty_state_title', 'No Live Namespace Available')
