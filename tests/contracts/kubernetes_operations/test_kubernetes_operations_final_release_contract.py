from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_operations_mutation_pages_use_the_canonical_full_width_v2_workspace() -> None:
    paths = (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/update.html',
        'app/templates/kubernetes_operations/configmaps/delete.html',
        'app/templates/kubernetes_operations/secrets/create.html',
        'app/templates/kubernetes_operations/secrets/replace.html',
        'app/templates/kubernetes_operations/secrets/delete.html',
        'app/templates/kubernetes_operations/secrets/reveal.html',
        'app/templates/kubernetes_operations/secrets/tls_rotation.html',
    )

    for relative in paths:
        source = read(relative)
        assert 'data-kubernetes-operation-layout="full-width-v2"' in source
        assert 'context_rail.html' not in source


def test_shared_operation_component_owns_sections_workflows_guardrails_and_embedded_actions() -> None:
    component = read('app/templates/components/kubernetes_operation_ui.html')

    assert 'macro workspace_section' in component
    assert 'macro workflow_control' in component
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'components/operational_point_flow.html' in component
    assert 'embedded=true' in component


def test_operations_authorization_and_cluster_prerequisite_are_owned_inside_route_permissions() -> None:
    root_routes = read('app/kubernetes_operations/routes.py')
    operation_flow = read('app/kubernetes_operations/operation_flow.py')

    assert '.before_request' not in root_routes
    assert 'has_registered_clusters' not in root_routes
    assert 'def cluster_required[' in operation_flow
    assert 'has_registered_clusters()' in operation_flow
    assert "request.headers.get('HX-Request') == 'true'" in operation_flow


def test_operations_release_evidence_is_documented_and_wired_to_the_quality_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    pattern = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')

    assert 'verify_kubernetes_operations_final_lock.py' in quality_gate
    assert 'tests/kubernetes_operations' in quality_gate
    assert 'test_kubernetes_operations_final_release_contract.py' in coverage
    assert 'Full-Width Mutation Workspace v2' in pattern
