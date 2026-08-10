from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_management_landings_use_flat_operational_workflow_catalog() -> None:
    component = read('app/templates/components/operational_workflow_card.html')
    catalog = read('app/templates/components/operational_workflow_catalog.html')
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
        assert 'min-h-[23rem]' not in source


def test_live_mutation_pages_use_full_width_v2_without_content_rails() -> None:
    pages = (
        'configmaps/create.html',
        'configmaps/update.html',
        'configmaps/delete.html',
        'secrets/create.html',
        'secrets/replace.html',
        'secrets/delete.html',
        'secrets/reveal.html',
        'secrets/tls_rotation.html',
    )
    for relative in pages:
        source = (TEMPLATES / 'kubernetes_operations' / relative).read_text(encoding='utf-8')
        assert 'operation_evidence_boundary.html' in source
        assert 'data-kubernetes-operation-layout="full-width-v2"' in source
        assert 'context_rail.html' not in source
        assert 'context_rail.layout_classes' not in source
        assert 'context_rail.rail_classes' not in source


def test_crud_workflows_use_shared_full_width_control_section() -> None:
    for relative in (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/update.html',
        'app/templates/kubernetes_operations/configmaps/delete.html',
        'app/templates/kubernetes_operations/secrets/create.html',
        'app/templates/kubernetes_operations/secrets/replace.html',
        'app/templates/kubernetes_operations/secrets/delete.html',
        'app/templates/kubernetes_operations/secrets/reveal.html',
        'app/templates/kubernetes_operations/secrets/tls_rotation.html',
    ):
        source = read(relative)
        assert 'secret_ui.workflow_control(' in source or 'configmap_ui.workflow_control(' in source
        assert 'information_guide_card.html' not in source
        assert 'info_flow.html' not in source

    component = read('app/templates/components/kubernetes_operation_ui.html')
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'point_flow.render' in component
    assert 'embedded=true' in component


def test_single_tls_rotation_uses_full_width_integrated_workspace() -> None:
    source = read('app/templates/kubernetes_operations/secrets/tls_rotate.html')
    assert 'context_rail.html' not in source
    assert 'Replacement Certificate Pair & Validation' in source
    assert 'embedded=true' in source
    assert 'Controlled Rotation & Governance Posture' in source
    assert 'operational_point_flow.html' in source
    assert 'TLS Certificate Posture' in source
    assert 'Open Certificate Details' in source


def test_secret_create_uses_reusable_choice_and_entry_components() -> None:
    source = read('app/templates/kubernetes_operations/secrets/create.html')
    configmap_editor = read('app/templates/kubernetes_operations/configmaps/_entries_editor.html')
    assert 'components/choice_card_group.html' in source
    assert 'choice_cards.option(' in source
    assert 'lg:grid-cols-3' in source
    assert 'xl:grid-cols-5' not in source
    assert 'components/structured_entry_editor.html' in source
    assert 'entry_editor.row_classes' in source
    assert 'components/structured_entry_editor.html' in configmap_editor
    assert 'Target & Identity' in source
    assert 'xl:grid-cols-4' in source


def test_operation_permission_and_classification_are_separate() -> None:
    component = read('app/templates/components/operational_workflow_card.html')
    assert "'Available' if allowed else 'Restricted'" in component
    assert 'metadata_label(classification' in component
    assert "status_label('Protected'" not in component


def test_operation_templates_use_canonical_control_geometry() -> None:
    operation_root = TEMPLATES / 'kubernetes_operations'
    for template in operation_root.rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        assert 'min-h-[23rem]' not in source, template
        assert 'text-[10px]' not in source, template
        assert 'text-[11px]' not in source, template
        assert 'tracking-[0.' not in source, template


def test_bulk_tls_rotation_uses_full_width_workflow_control() -> None:
    source = read('app/templates/kubernetes_operations/secrets/tls_rotation.html')
    assert 'secret_ui.workflow_control(' in source
    assert 'Controlled Bulk TLS Rotation' in source
    assert 'view_more_content.html' not in source
    assert 'view_more.render(' not in source
    assert 'context_rail.html' not in source
    assert 'data-validation-apply' in source


def test_operation_catalog_owns_a_stable_action_column() -> None:
    component = read('app/templates/components/operational_workflow_card.html')
    assert 'minmax(12rem,0.56fr)' in component
    assert 'lg:justify-self-stretch' in component
    assert "action_button.classes('secondary', false) }} w-full justify-center" in component
    assert 'min-h-9 w-full items-center justify-center' in component
