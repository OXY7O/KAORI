from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OPERATION_TEMPLATES = (
    'app/templates/kubernetes/operations/configmaps/create.html',
    'app/templates/kubernetes/operations/configmaps/update.html',
    'app/templates/kubernetes/operations/configmaps/delete.html',
    'app/templates/kubernetes/operations/secrets/create.html',
    'app/templates/kubernetes/operations/secrets/replace.html',
    'app/templates/kubernetes/operations/secrets/delete.html',
    'app/templates/kubernetes/operations/secrets/reveal.html',
)


def test_shared_operation_ui_retains_special_full_width_workflow_primitive() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'macro workflow_control' in component
    assert 'components/operational_point_flow.html' in component
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'form_action_bar.render' in component
    assert 'embedded=true' in component


def test_reviewed_configmap_secret_crud_and_reveal_use_form_with_right_context() -> None:
    for relative in OPERATION_TEMPLATES:
        template = (ROOT / relative).read_text(encoding='utf-8')
        assert 'data-kubernetes-operation-layout="form-context-v1"' in template
        assert 'components/form_with_context_rail.html' in template
        assert 'form_context.layout_classes()' in template
        assert 'form_context.main_classes()' in template
        assert 'form_context.rail_classes()' in template
        assert 'components/info_flow.html' in template
        assert 'components/information_guide_card.html' in template
        assert 'workflow_control(' not in template


def test_tls_rotation_keeps_its_dedicated_full_width_workflow() -> None:
    template = (ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotation.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="full-width-v2"' in template
    assert 'workflow_control(' in template
