from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_configmap_create_uses_guided_full_width_reference_workspace() -> None:
    template = (ROOT / 'app/templates/kubernetes_operations/configmaps/create.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="full-width-v2"' in template
    assert 'data-kubernetes-operation-experience="guided-v3"' in template
    assert 'Define ConfigMap' in template
    assert 'Creation Safety' in template
    assert 'Add ConfigMap Data' in template
    assert 'Review & Create' in template
    assert 'How This Works' in template
    assert 'configmap_ui.guidance_panel(' in template
    assert 'configmap_ui.action_bar(' in template
    assert 'configmap_ui.workflow_control(' not in template
    assert 'context_rail.html' not in template
    assert 'information_guide_card.html' not in template


def test_shared_operation_ui_owns_guidance_and_embedded_action_geometry() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'macro guidance_panel' in component
    assert 'data-kubernetes-operation-guidance' in component
    assert 'macro workflow_control' in component
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'form_action_bar.render' in component
    assert 'embedded=true' in component
