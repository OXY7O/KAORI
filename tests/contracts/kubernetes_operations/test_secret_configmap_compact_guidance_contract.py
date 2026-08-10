from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OPERATION_TEMPLATES = (
    'app/templates/kubernetes_operations/configmaps/create.html',
    'app/templates/kubernetes_operations/configmaps/update.html',
    'app/templates/kubernetes_operations/configmaps/delete.html',
    'app/templates/kubernetes_operations/secrets/create.html',
    'app/templates/kubernetes_operations/secrets/replace.html',
    'app/templates/kubernetes_operations/secrets/delete.html',
)


def test_shared_operation_ui_owns_full_width_workflow_guidance() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'macro workflow_control' in component
    assert 'components/operational_point_flow.html' in component
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'form_action_bar.render' in component
    assert 'embedded=true' in component


def test_configmap_create_uses_the_shared_right_context_rail_while_other_crud_remains_migration_scope() -> None:
    create = (ROOT / 'app/templates/kubernetes_operations/configmaps/create.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="context-rail-v4"' in create
    assert 'data-kubernetes-operation-experience="task-focused-v4"' in create
    assert 'components/context_rail.html' in create
    assert 'components/info_flow.html' in create
    assert 'components/information_guide_card.html' in create
    assert "context_rail.layout_classes('wide')" in create
    assert 'workflow_control(' not in create

    for relative in OPERATION_TEMPLATES[1:]:
        template = (ROOT / relative).read_text(encoding='utf-8')
        assert 'data-kubernetes-operation-layout="full-width-v2"' in template
        assert 'workflow_control(' in template
