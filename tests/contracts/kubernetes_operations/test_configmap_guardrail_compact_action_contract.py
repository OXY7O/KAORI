from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_configmap_create_uses_full_width_shared_workflow_guardrails() -> None:
    template = (ROOT / 'app/templates/kubernetes_operations/configmaps/create.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="full-width-v2"' in template
    assert 'configmap_ui.workflow_control(' in template
    assert 'context_rail.html' not in template
    assert 'information_guide_card.html' not in template


def test_shared_operation_workflow_control_owns_guardrail_and_action_geometry() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'sm:grid-cols-2 xl:grid-cols-4' in component
    assert 'form_action_bar.render' in component
    assert 'embedded=true' in component
