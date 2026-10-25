from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OPERATION_TEMPLATES = (
    'app/templates/kubernetes/operations/configmaps/create.html',
    'app/templates/kubernetes/operations/configmaps/update.html',
    'app/templates/kubernetes/operations/configmaps/delete.html',
    'app/templates/kubernetes/operations/secrets/create.html',
    'app/templates/kubernetes/operations/secrets/replace.html',
    'app/templates/kubernetes/operations/secrets/delete.html',
    'app/templates/kubernetes/operations/secrets/reveal.html',
)


def test_shared_operation_ui_retains_special_full_width_workflow_primitive() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'macro workflow_control' in component
    assert 'components/operational_point_flow.html' in component
    assert 'data-kubernetes-operation-workflow' in component
    assert 'data-kubernetes-operation-guardrails' in component
    assert 'form_action_bar.render' in component
    assert 'embedded=true' in component


def test_reviewed_configmap_secret_crud_and_reveal_use_form_with_right_context() -> None:
    for relative in OPERATION_TEMPLATES:
        template = (ROOT / relative).read_text(encoding='utf-8')
        assert 'data-kubernetes-operation-layout="form-context-v1"' in template
        assert 'components/form_with_context_rail.html' in template
        assert 'form_context.layout_classes()' in template
        assert 'form_context.main_classes()' in template
        assert 'form_context.rail_classes()' in template
        assert 'components/info_flow.html' in template
        assert 'components/information_guide_card.html' in template
        assert 'workflow_control(' not in template


def test_tls_rotation_keeps_its_dedicated_full_width_workflow() -> None:
    template = (ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotation.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="full-width-v2"' in template
    assert 'workflow_control(' in template


def test_configmap_and_bulk_tls_guidance_is_compact_without_weakening_safety() -> None:
    create = (ROOT / 'app/templates/kubernetes/operations/configmaps/create.html').read_text(encoding='utf-8')
    update = (ROOT / 'app/templates/kubernetes/operations/configmaps/update.html').read_text(encoding='utf-8')
    delete = (ROOT / 'app/templates/kubernetes/operations/configmaps/delete.html').read_text(encoding='utf-8')
    rotation = (ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotation.html').read_text(encoding='utf-8')

    assert 'Audit records metadata, never ConfigMap values.' in create
    assert 'Read live data and immutability before editing.' in update
    assert "'Update Safety Contract', 'Active safeguards for this update.'" in update
    assert 'Controls that stay active while the live object is edited.' not in update
    assert 'Check exact name and RBAC without DELETE.' in delete
    assert "note='Irreversible and resourceVersion-bound.'" in delete
    assert 'Final deletion is irreversible from KAORI and must target the same validated resourceVersion.' not in delete
    target = (ROOT / 'app/templates/kubernetes/operations/configmaps/_delete_target.html').read_text(
        encoding='utf-8'
    )
    modal = (ROOT / 'app/templates/components/destructive_confirmation_modal.html').read_text(
        encoding='utf-8'
    )
    assert "won't restart workloads; Pods may fail" in target
    assert "Delete uses validated target and resourceVersion; Cancel keeps it unchanged." in modal
    assert 'Only explicitly checked TLS Secrets can be updated; all unselected targets remain untouched.' in rotation
    assert 'Validate the uploaded certificate pair and every selected TLS Secret before applying an update.' in rotation
    assert "workflow_control('Controlled Bulk TLS Rotation'" in rotation


def test_secret_delete_confirmation_copy_is_compact_and_keeps_safety_context() -> None:
    delete = (ROOT / 'app/templates/kubernetes/operations/secrets/delete.html').read_text(
        encoding='utf-8'
    )

    assert "notice='Confirm deletion; Secret values stay hidden.'" in delete
    assert 'Confirm removal of the validated live Secret. Secret values remain hidden.' not in delete
    assert "'The receipt binds deletion to reviewed resourceVersion.'" in delete
    assert "'No DELETE in Validation'" in delete
    assert "presentation='kubernetes'" in delete


def test_review7_operation_titles_use_shared_violet_guide_not_legacy_question_icon() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert "variant='guide'" in component
    assert 'flex min-h-6 flex-wrap items-center gap-2' in component
    assert 'info_tip.render(info_id, info_title, info_text, info_items' in component
    assert 'components/info_tip.html' in component


def test_review7_compact_operations_copy_keeps_server_safety_semantics() -> None:
    create = (ROOT / 'app/templates/kubernetes/operations/configmaps/create.html').read_text(encoding='utf-8')
    update = (ROOT / 'app/templates/kubernetes/operations/configmaps/update.html').read_text(encoding='utf-8')
    delete = (ROOT / 'app/templates/kubernetes/operations/configmaps/delete.html').read_text(encoding='utf-8')
    secret_create = (ROOT / 'app/templates/kubernetes/operations/secrets/create.html').read_text(encoding='utf-8')
    secret_delete = (ROOT / 'app/templates/kubernetes/operations/secrets/delete.html').read_text(encoding='utf-8')

    for phrase, source in (
        ('Existing ConfigMaps are never overwritten.', create),
        ('Create requires the latest server-side dry-run.', create),
        ('Audit records metadata, never ConfigMap values.', create),
        ('Review added, changed, removed, and unchanged keys.', update),
        ('Immutable ConfigMaps cannot be mutated.', update),
        ('resourceVersion blocks stale updates.', update),
        ('Check exact name and RBAC without DELETE.', delete),
        ('Delete the same resource once using the receipt.', delete),
        ('Secret values are never stored by KAORI.', secret_create),
        ('Audit records metadata, never Secret values.', secret_create),
        ('Verify name, version, and RBAC without DELETE.', secret_delete),
        ('The receipt binds deletion to reviewed resourceVersion.', secret_delete),
    ):
        assert phrase in source
