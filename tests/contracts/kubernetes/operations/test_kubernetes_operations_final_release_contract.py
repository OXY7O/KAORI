from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_operations_ordinary_crud_and_protected_reveal_use_form_with_right_context() -> None:
    paths = (
        'app/templates/kubernetes/operations/configmaps/create.html',
        'app/templates/kubernetes/operations/configmaps/update.html',
        'app/templates/kubernetes/operations/configmaps/delete.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/replace.html',
        'app/templates/kubernetes/operations/secrets/delete.html',
        'app/templates/kubernetes/operations/secrets/reveal.html',
    )

    for relative in paths:
        source = read(relative)
        assert 'data-kubernetes-operation-layout="form-context-v1"' in source
        assert 'components/form_with_context_rail.html' in source
        assert 'form_context.layout_classes()' in source
        assert 'form_context.rail_classes()' in source
        assert 'workflow_control(' not in source


def test_special_tls_rotation_retains_reviewed_full_width_workspace() -> None:
    source = read('app/templates/kubernetes/operations/secrets/tls_rotation.html')
    assert 'data-kubernetes-operation-layout="full-width-v2"' in source
    assert 'workflow_control(' in source


def test_shared_operation_component_keeps_special_workflow_and_embedded_action_primitives() -> None:
    component = read('app/templates/components/kubernetes_operation_ui.html')
    assert 'macro workspace_section' in component
    assert 'macro workflow_control' in component
    assert 'components/operational_point_flow.html' in component
    assert 'embedded=true' in component


def test_operations_landing_hero_and_deletion_reference_defaults_are_aligned() -> None:
    configmaps = read('app/templates/kubernetes/operations/configmaps/index.html')
    secrets = read('app/templates/kubernetes/operations/secrets/index.html')
    configmap_delete = read('app/templates/kubernetes/operations/configmaps/delete.html')
    secret_delete = read('app/templates/kubernetes/operations/secrets/delete.html')

    for landing in (configmaps, secrets):
        assert "'Open Cluster Integrations'," in landing
        assert "'Manage Clusters'," not in landing
        assert "url_for('integrations.kubernetes')" in landing

    assert "information_guide_card.render('Deletion Safety Contract'" in configmap_delete
    assert "configmap_delete_guardrails, icon='shield-alert', open_by_default=false" in configmap_delete
    assert "information_guide_card.render('Deletion Safety Contract'" in secret_delete
    assert "secret_delete_guardrails, icon='shield-alert', open_by_default=false" in secret_delete


def test_operations_workflow_hero_names_are_compact_and_semantically_distinct() -> None:
    configmap_create = read('app/templates/kubernetes/operations/configmaps/create.html')
    secret_create = read('app/templates/kubernetes/operations/secrets/create.html')
    secret_replace = read('app/templates/kubernetes/operations/secrets/replace.html')
    configmap_routes = read('app/kubernetes/operations/configmaps/routes.py')
    secret_routes = read('app/kubernetes/operations/secrets/crud_routes.py')
    pattern = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')

    assert '>Create ConfigMap</h1>' in configmap_create
    assert '>Create Kubernetes ConfigMap</h1>' not in configmap_create
    assert '>Create Secret</h1>' in secret_create
    assert 'Create Kubernetes Secret' not in secret_create
    assert '>Replace Secret</h1>' in secret_replace
    assert 'Replace Kubernetes Secret Data' not in secret_replace

    assert "page_title='Create ConfigMap'" in configmap_routes
    assert "page_title='Create Secret'" in secret_routes
    assert "page_title='Replace Secret'" in secret_routes
    assert '**Update ConfigMap**' in pattern and '**Replace Secret**' in pattern
    assert 'without reading or rendering current Secret values' in pattern


def test_operations_authorization_and_cluster_prerequisite_are_owned_inside_route_permissions() -> None:
    root_routes = read('app/kubernetes/operations/routes.py')
    operation_flow = read('app/kubernetes/operations/operation_flow.py')

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
    assert "-m 'not debug and not e2e and not contract and not migration'" in quality_gate
    assert 'test_kubernetes_operations_final_release_contract.py' in coverage
    assert 'tests/unit/kubernetes/operations/test_operation_flow_unit.py' in coverage
    assert 'tests/unit/kubernetes/operations/test_operation_flow.py' not in coverage
    assert 'Task-Fit Layout v7' in pattern
