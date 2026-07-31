from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


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


def test_form_action_bar_is_a_rounded_workspace_control_not_a_flat_strip() -> None:
    action_bar = _read('app/templates/components/form_action_bar.html')

    assert 'rounded-xl' in action_bar
    assert 'border border-outline-default' in action_bar
    assert 'bg-surface-card' in action_bar
    assert 'border-t border-outline-subtle bg-surface-hover' not in action_bar


def test_bulk_tls_flow_is_expandable_point_flow() -> None:
    template = _read('app/templates/kubernetes_operations/secrets/tls_rotation.html')
    component = _read('app/templates/components/operational_point_flow.html')

    assert 'view_more.render(' in template
    assert 'point_flow.render' in template
    assert 'open_by_default=false' in template
    assert 'operational_flow_steps.render' not in template
    assert '<ol' in component
    assert 'rounded-xl border' not in component
