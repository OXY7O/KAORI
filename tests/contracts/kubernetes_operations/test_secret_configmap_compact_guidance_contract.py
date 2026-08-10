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


def test_secret_and_configmap_crud_pages_do_not_restore_right_rail_guidance() -> None:
    for relative in OPERATION_TEMPLATES:
        template = (ROOT / relative).read_text(encoding='utf-8')
        assert 'data-kubernetes-operation-layout="full-width-v2"' in template
        assert 'context_rail.html' not in template
        assert 'information_guide_card.html' not in template
        assert 'info_flow.html' not in template
        if relative.endswith('configmaps/create.html'):
            assert 'data-kubernetes-operation-experience="guided-v3"' in template
            assert 'guidance_panel(' in template
            assert 'workflow_control(' not in template
        else:
            assert 'workflow_control(' in template
