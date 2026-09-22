import json
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
    assert '{{ table_ui.block_classes() }}' in catalog
    assert 'Validation Boundary' not in component
    assert 'Authority Boundary' not in component

    for relative in (
        'app/templates/kubernetes/operations/configmaps/index.html',
        'app/templates/kubernetes/operations/secrets/index.html',
    ):
        source = read(relative)
        assert 'operation_evidence_boundary.html' in source
        assert 'operational_workflow_card.html' in source
        assert 'operational_workflow_catalog.html' in source
        assert 'workflow_catalog.render' in source
        assert 'min-h-[23rem]' not in source


def test_reviewed_crud_and_protected_reveal_use_form_with_right_context() -> None:
    pages = (
        'configmaps/create.html',
        'configmaps/update.html',
        'configmaps/delete.html',
        'secrets/create.html',
        'secrets/replace.html',
        'secrets/delete.html',
        'secrets/reveal.html',
    )
    for relative in pages:
        source = (TEMPLATES / 'kubernetes' / 'operations' / relative).read_text(encoding='utf-8')
        assert 'operation_evidence_boundary.html' in source
        assert 'data-kubernetes-operation-layout="form-context-v1"' in source
        assert 'components/form_with_context_rail.html' in source
        assert 'form_context.layout_classes()' in source
        assert 'form_context.rail_classes()' in source
        assert 'info_flow.html' in source
        assert 'information_guide_card.html' in source


def test_reviewed_crud_moves_workflow_guidance_to_right_context() -> None:
    for relative in (
        'app/templates/kubernetes/operations/configmaps/create.html',
        'app/templates/kubernetes/operations/configmaps/update.html',
        'app/templates/kubernetes/operations/configmaps/delete.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/replace.html',
        'app/templates/kubernetes/operations/secrets/delete.html',
        'app/templates/kubernetes/operations/secrets/reveal.html',
    ):
        source = read(relative)
        assert 'workflow_control(' not in source
        assert 'information_guide_card.html' in source
        assert 'info_flow.html' in source

    component = read('app/templates/components/kubernetes_operation_ui.html')
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'point_flow.render' in component
    assert 'embedded=true' in component


def test_single_tls_rotation_uses_full_width_integrated_workspace() -> None:
    source = read('app/templates/kubernetes/operations/secrets/tls_rotate.html')
    assert 'context_rail.html' not in source
    assert 'Replacement Certificate Pair & Validation' in source
    assert 'embedded=true' in source
    assert 'Controlled Rotation & Governance Posture' in source
    assert 'operational_point_flow.html' in source
    assert 'TLS Certificate Posture' in source
    assert 'Open Certificate Details' in source


def test_secret_create_uses_reusable_choice_and_entry_components() -> None:
    source = read('app/templates/kubernetes/operations/secrets/create.html')
    configmap_editor = read('app/templates/kubernetes/operations/configmaps/_entries_editor.html')
    assert 'components/choice_card_group.html' in source
    assert 'choice_cards.option(' in source
    assert 'lg:grid-cols-3' in source
    assert 'xl:grid-cols-5' not in source
    assert 'components/structured_entry_editor.html' in source
    assert 'entry_editor.row_classes' in source
    assert 'components/structured_entry_editor.html' in configmap_editor
    assert 'Target & Identity' in source
    assert 'grid gap-5 md:grid-cols-2' in source
    assert 'lg:grid-cols-2 xl:grid-cols-4' not in source


def test_operation_permission_and_classification_are_separate() -> None:
    component = read('app/templates/components/operational_workflow_card.html')
    assert "'Available' if allowed else 'Restricted'" in component
    assert 'metadata_label(classification' in component
    assert "status_label('Protected'" not in component


def test_operation_templates_use_canonical_control_geometry() -> None:
    operation_root = TEMPLATES / 'kubernetes' / 'operations'
    for template in operation_root.rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        assert 'min-h-[23rem]' not in source, template
        assert 'text-[10px]' not in source, template
        assert 'text-[11px]' not in source, template
        assert 'tracking-[0.' not in source, template


def test_bulk_tls_rotation_uses_full_width_workflow_control() -> None:
    source = read('app/templates/kubernetes/operations/secrets/tls_rotation.html')
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


def test_live_target_selectors_keep_consistent_helper_context() -> None:
    configmap_create = read('app/templates/kubernetes/operations/configmaps/create.html')
    configmap_workspace = read('app/templates/kubernetes/operations/configmaps/_workspace.html')
    secret_create = read('app/templates/kubernetes/operations/secrets/create.html')
    secret_namespace = read('app/templates/kubernetes/operations/secrets/_namespace_field.html')
    secret_replace = read('app/templates/kubernetes/operations/secrets/replace.html')
    secret_delete = read('app/templates/kubernetes/operations/secrets/delete.html')
    secret_reveal = read('app/templates/kubernetes/operations/secrets/reveal.html')

    assert 'Registered cluster for the target namespace.' in configmap_create
    assert 'Registered cluster for the target namespace.' in configmap_workspace
    assert 'Loaded from the selected Kubernetes API.' in configmap_workspace
    assert 'Loaded from the selected live namespace.' in configmap_workspace
    assert 'Registered cluster for the target namespace.' in secret_create
    assert 'Loaded from the selected Kubernetes API.' in secret_namespace
    assert 'Registered cluster for the target namespace.' in secret_replace
    assert 'Registered cluster for the target namespace.' in secret_delete
    assert 'Protected clusters are registered live targets for Secret Reveal.' in secret_reveal


def test_operation_hero_copy_keeps_explicit_live_validation_boundaries() -> None:
    configmap_routes = read('app/kubernetes/operations/configmaps/routes.py')
    secret_routes = read('app/kubernetes/operations/secrets/crud_routes.py')
    reveal_routes = read('app/kubernetes/operations/secrets/reveal_routes.py')
    tls_routes = read('app/kubernetes/operations/secrets/tls_routes.py')

    assert (
        'Manage ConfigMaps through validated, auditable workflows in KAORI.'
        in configmap_routes
    )
    assert (
        'Preview and validate one ConfigMap update before applying safely.'
        in configmap_routes
    )
    assert 'Validate the live ConfigMap target before governed removal.' in configmap_routes
    assert 'Create one validated Secret without persisting sensitive values.' in secret_routes
    assert (
        'Replace selected Secret keys without reading current values.'
        in secret_routes
    )
    assert 'Validate the exact Secret target before confirming governed removal.' in secret_routes
    assert (
        'Reveal one Secret key through protected, audited access in KAORI.'
        in reveal_routes
    )
    assert (
        'Validate a certificate pair before controlled TLS Secret rotation.' in tls_routes
    )


def test_secret_operation_surface_debt_uses_shared_style_authorities() -> None:
    semantic_templates = (
        'app/templates/kubernetes/operations/secrets/_delete_target.html',
        'app/templates/kubernetes/operations/secrets/_replace_content_form.html',
        'app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html',
        'app/templates/kubernetes/operations/secrets/_reveal_value.html',
        'app/templates/kubernetes/operations/secrets/_update_preview.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/tls_rotation.html',
    )
    shared_shell_templates = (
        'app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/tls_rotation.html',
    )
    baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json'))
    callout = read('app/templates/components/operational_callout.html')

    assert 'macro semantic_hover_border_classes' in callout

    for relative in semantic_templates:
        source = read(relative)
        assert 'components/operational_callout.html' in source
        assert 'border-status-' not in source
        assert 'operational_callout.semantic_border_classes(' in source
        assert relative not in baseline['files']

    for relative in shared_shell_templates:
        source = read(relative)
        assert 'components/kubernetes_operation_ui.html' in source
        assert 'secret_ui.surface_shell_classes' in source
        assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' not in source
