from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_management_landings_use_operational_workflow_catalog() -> None:
    for relative in (
        'app/templates/kubernetes_operations/configmaps/index.html',
        'app/templates/kubernetes_operations/secrets/index.html',
    ):
        source = read(relative)
        assert 'operation_evidence_boundary.html' in source
        assert 'operational_workflow_card.html' in source
        assert 'Operational Workflow Catalog' in source
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
        assert 'context_rail.layout_classes()' in source
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
