from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_management_catalog_actions_are_compact_and_not_filled_blocks() -> None:
    component = _read('app/templates/components/operational_workflow_card.html')
    configmap = _read('app/templates/kubernetes_operations/configmaps/index.html')
    secret = _read('app/templates/kubernetes_operations/secrets/index.html')
    assert "action_button.classes('secondary', false)" in component
    assert "action_button.classes('primary', true)" not in component
    assert 'lg:w-48' not in component
    assert "'Create'," in configmap
    assert "'Update'," in configmap
    assert "'Delete'," in configmap
    assert "'Replace'," in secret
    assert "'Open Reveal'," in secret
    assert "'Bulk Rotation' if can_rotate_bulk" in secret


def test_form_action_bar_supports_standalone_and_embedded_workspace_controls() -> None:
    action_bar = _read('app/templates/components/form_action_bar.html')
    operation_ui = _read('app/templates/components/kubernetes_operation_ui.html')
    assert 'embedded=false' in action_bar
    assert 'rounded-xl border border-outline-default bg-surface-card shadow-sm' in action_bar
    assert 'border-t border-outline-subtle bg-surface-subtle' in action_bar
    assert 'form_action_bar.render' in operation_ui
    assert 'embedded=true' in operation_ui


def test_bulk_tls_flow_uses_always_visible_shared_workflow_control() -> None:
    template = _read('app/templates/kubernetes_operations/secrets/tls_rotation.html')
    component = _read('app/templates/components/kubernetes_operation_ui.html')
    point_flow = _read('app/templates/components/operational_point_flow.html')
    assert 'secret_ui.workflow_control(' in template
    assert 'view_more.render(' not in template
    assert 'Controlled Bulk TLS Rotation' in template
    assert 'point_flow.render' in component
    assert '<ol' in point_flow
    assert 'rounded-xl border' not in point_flow
