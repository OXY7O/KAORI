from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_management_landings_use_flat_operational_workflow_catalog() -> None:
    component = read('app/templates/components/operational_workflow_card.html')
    assert 'border-t border-outline-subtle' in component
    assert 'first:border-t-0' in component
    assert 'hover:bg-surface-hover' in component
    assert 'rounded-xl border border-outline-default' in catalog
    assert 'Validation Boundary' not in component
    assert 'Authority Boundary' not in component

    for relative in (
        'app/templates/kubernetes_operations/configmaps/index.html',
        'app/templates/kubernetes_operations/secrets/index.html',
    ):
        source = read(relative)
        assert 'operation_evidence_boundary.html' in source
        assert 'operational_workflow_card.html' in source
        assert 'operational_workflow_catalog.html' in source
        assert 'workflow_catalog.render' in source
        assert 'grid items-start gap-4' not in source
        assert 'min-h-[23rem]' not in source


def test_live_mutation_pages_use_canonical_evidence_and_context_rail() -> None:
    pages = (
        'configmaps/create.html',
        'configmaps/update.html',
        'configmaps/delete.html',
        'secrets/create.html',
        'secrets/replace.html',
        'secrets/delete.html',
        'secrets/tls_rotate.html',
    )
    for relative in pages:
        source = (TEMPLATES / 'kubernetes_operations' / relative).read_text()
        assert 'operation_evidence_boundary.html' in source
        assert 'context_rail.html' in source
        assert "context_rail.layout_classes('wide')" in source
        assert 'context_rail.main_classes()' in source
        assert 'context_rail.rail_classes()' in source
        assert 'xl:grid-cols-[minmax(0,1fr)_' not in source


def test_secret_create_uses_reusable_choice_and_entry_components() -> None:
    source = read('app/templates/kubernetes_operations/secrets/create.html')
    configmap_editor = read('app/templates/kubernetes_operations/configmaps/_entries_editor.html')

    assert 'components/choice_card_group.html' in source
    assert 'choice_cards.option(' in source
    assert 'lg:grid-cols-3' in source
    assert 'lg:grid-cols-5' not in source
    assert 'components/structured_entry_editor.html' in source
    assert 'entry_editor.row_classes' in source
    assert 'components/structured_entry_editor.html' in configmap_editor


def test_operation_permission_and_classification_are_separate() -> None:
    component = read('app/templates/components/operational_workflow_card.html')
    assert "'Available' if allowed else 'Restricted'" in component
    assert 'metadata_label(classification' in component
    assert "status_label('Protected'" not in component


def test_operation_templates_use_canonical_control_geometry() -> None:
    operation_root = TEMPLATES / 'kubernetes_operations'
    for template in operation_root.rglob('*.html'):
        source = template.read_text()
        assert 'min-h-[23rem]' not in source, template
        assert 'text-[10px]' not in source, template
        assert 'text-[11px]' not in source, template
        assert 'tracking-[0.' not in source, template


def test_secondary_operation_rail_guidance_is_collapsed_by_default() -> None:
    configmap_pages = (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/update.html',
        'app/templates/kubernetes_operations/configmaps/delete.html',
    )
    for relative in configmap_pages:
        source = read(relative)
        assert 'information_guide_card.html' in source
        assert 'open_by_default=false' in source

    create_secret = read('app/templates/kubernetes_operations/secrets/create.html')
    replace_secret = read('app/templates/kubernetes_operations/secrets/replace.html')
    delete_secret = read('app/templates/kubernetes_operations/secrets/delete.html')
    assert 'view_more_content.html' in create_secret
    assert "'Creation Summary'" in create_secret
    assert 'open_by_default=true' in create_secret
    assert 'open_by_default=false' in create_secret
    assert 'open_by_default=false' in replace_secret
    assert 'open_by_default=false' in delete_secret


def test_secret_create_selection_and_actions_are_visually_owned_by_main_workspace() -> None:
    choice = read('app/templates/components/choice_card_group.html')
    create = read('app/templates/kubernetes_operations/secrets/create.html')

    styles = read('frontend/styles.css')
    assert 'secret-type-choice' in choice
    assert 'secret-type-input sr-only' in choice
    assert 'secret-type-selected-indicator' in choice
    assert 'x-show=' not in choice
    assert '@change="{{ model }} = $event.target.value"' in choice
    assert 'box-shadow: inset 3px 0 0 var(--kaori-brand-primary)' not in styles
    assert 'box-shadow: 0 8px 20px rgba(5, 3, 9, 0.24)' in styles
    assert '0 0 0 2px var(--kaori-brand-primary)' not in styles
    assert '.secret-type-input:checked + .secret-type-option .secret-type-selected-indicator' in styles
    assert 'border border-brand-outline bg-kaori-soft' in choice

    action_index = create.index("secret_ui.action_bar('scan-search', 'Validate Before Creation'")
    aside_index = create.index('<aside class="{{ context_rail.rail_classes() }}')
    assert action_index < aside_index


def test_bulk_tls_rotation_uses_expandable_operational_point_flow() -> None:
    source = read('app/templates/kubernetes_operations/secrets/tls_rotation.html')

    assert 'components/operational_point_flow.html' in source
    assert 'point_flow.render' in source
    assert 'view_more.render(' in source
    assert 'Controlled TLS Rotation Flow' in source
    assert 'open_by_default=false' in source
    assert 'components/operational_flow_steps.html' not in source
    assert 'xl:grid-cols-3 xl:items-start' not in source
    assert "secret_ui.action_bar('shield-check', 'Validate Before Bulk Rotation'" in source


def test_operation_catalog_owns_a_stable_action_column() -> None:
    component = read('app/templates/components/operational_workflow_card.html')

    assert 'minmax(12rem,0.56fr)' in component
    assert 'lg:justify-self-stretch' in component
    assert "action_button.classes('secondary', false) }} w-full justify-center" in component
    assert 'min-h-9 w-full items-center justify-center' in component
