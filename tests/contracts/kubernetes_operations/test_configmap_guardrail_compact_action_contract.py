from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_configmap_create_uses_task_focused_context_rail_reference_workspace() -> None:
    template = (ROOT / 'app/templates/kubernetes_operations/configmaps/create.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="context-rail-v4"' in template
    assert 'data-kubernetes-operation-experience="task-focused-v4"' in template
    assert 'context_rail.layout_classes(\'wide\')' in template
    assert 'context_rail.rail_classes()' in template
    assert 'Target & Identity' in template
    assert 'ConfigMap Data' in template
    assert 'Create ConfigMap Flow' in template
    assert 'Creation Guardrails' in template
    assert 'info_flow.render(' in template
    assert 'information_guide_card.render(' in template
    assert 'configmap_ui.action_bar(' in template
    assert 'configmap_ui.workflow_control(' not in template


def test_shared_operation_ui_keeps_reusable_section_and_action_geometry() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'macro workspace_section' in component
    assert 'macro workflow_control' in component
    assert 'components/operational_point_flow.html' in component
    assert 'form_action_bar.render' in component
