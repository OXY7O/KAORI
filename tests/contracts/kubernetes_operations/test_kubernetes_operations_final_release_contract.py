from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_operations_ordinary_crud_and_protected_reveal_use_form_with_right_context() -> None:
    paths = (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/update.html',
        'app/templates/kubernetes_operations/configmaps/delete.html',
        'app/templates/kubernetes_operations/secrets/create.html',
        'app/templates/kubernetes_operations/secrets/replace.html',
        'app/templates/kubernetes_operations/secrets/delete.html',
        'app/templates/kubernetes_operations/secrets/reveal.html',
    )

    for relative in paths:
        source = read(relative)
        assert 'data-kubernetes-operation-layout="form-context-v1"' in source
        assert 'components/form_with_context_rail.html' in source
        assert 'form_context.layout_classes()' in source
        assert 'form_context.rail_classes()' in source
        assert 'workflow_control(' not in source


def test_special_tls_rotation_retains_reviewed_full_width_workspace() -> None:
    source = read('app/templates/kubernetes_operations/secrets/tls_rotation.html')
    assert 'data-kubernetes-operation-layout="full-width-v2"' in source
    assert 'workflow_control(' in source


def test_shared_operation_component_keeps_special_workflow_and_embedded_action_primitives() -> None:
    component = read('app/templates/components/kubernetes_operation_ui.html')
    assert 'macro surface_shell_classes' in component
    assert 'macro workspace_section' in component
    assert 'macro workflow_control' in component
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
    assert 'Task-Fit Layout v7' in pattern


def test_operations_surface_and_reveal_semantics_stay_shared() -> None:
    copied_shell = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
    for relative in (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/update.html',
        'app/templates/kubernetes_operations/configmaps/delete.html',
        'app/templates/kubernetes_operations/secrets/reveal.html',
        'app/templates/kubernetes_operations/secrets/_reveal_step_up.html',
        'app/templates/kubernetes_operations/secrets/_reveal_request_status.html',
    ):
        source = read(relative)
        assert copied_shell not in source

    request_status = read('app/templates/kubernetes_operations/secrets/_reveal_request_status.html')
    administration = read('app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html')
    assert "operational_callout.semantic_surface_classes('warning')" in request_status
    assert 'border-status-warning-border' not in request_status
    assert "operational_callout.semantic_border_classes('warning')" in administration
    assert 'border-status-warning-border' not in administration
