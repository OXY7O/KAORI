from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotation.html'
ROTATE_TEMPLATE = ROOT / 'app/templates/kubernetes/operations/secrets/tls_rotate.html'


def _template() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def _rotate_template() -> str:
    return ROTATE_TEMPLATE.read_text(encoding='utf-8')


def test_bulk_tls_rotation_uses_full_width_upload_target_and_workflow_sections() -> None:
    template = _template()
    assert 'data-kubernetes-operation-layout="full-width-v2"' in template
    assert 'Controlled Bulk TLS Rotation' in template
    assert 'Validate Before Bulk Rotation' in template
    assert 'id="tls-secret-update-form"' in template
    assert 'secret_ui.workflow_control(' in template
    assert 'view_more.render(' not in template
    assert 'Controlled File Boundary' in template
    assert 'context_rail.html' not in template
    assert 'lg:grid-cols-2' in template


def test_bulk_tls_rotation_actions_target_the_upload_form_after_full_width_recomposition() -> None:
    template = _template()
    form_start = template.index('id="tls-secret-update-form"')
    form_end = template.index('</form>', form_start)
    workflow_index = template.index("secret_ui.workflow_control('Controlled Bulk TLS Rotation'")
    assert form_end < workflow_index
    assert 'hx-include="#tls-secret-update-form"' in template[workflow_index:]
    assert 'Validate Selected' in template[workflow_index:]
    assert 'Update Selected' in template[workflow_index:]
    assert 'Validation Required' not in template
    assert 'Changing either uploaded file or the selected target set invalidates the previous preview.' in template


def test_bulk_tls_external_apply_buttons_follow_the_same_validated_form() -> None:
    """Both actions are outside the upload form and must receive its validation event."""
    import re

    template = _template()
    form_end = template.index('</form>', template.index('id="tls-secret-update-form"'))
    external_actions = template[form_end:]
    apply_buttons = [
        button
        for button in re.findall(r'<button\b[^>]*>', external_actions, re.DOTALL)
        if re.search(r'(?<![\w-])data-validation-apply(?=\s|>)', button)
    ]

    assert len(apply_buttons) == 2  # Primary Update Selected and confirmation-modal Update Selected.
    assert all('data-validation-form="tls-secret-update-form"' in button for button in apply_buttons)


def test_bulk_tls_confirmation_reuses_native_dialog_and_current_checked_target_scope() -> None:
    template = _template()
    assert 'data-kaori-dialog-open' in template
    assert 'data-dialog-target="bulk-tls-rotation-confirm-dialog"' in template
    assert '<dialog id="bulk-tls-rotation-confirm-dialog"' in template
    assert 'data-kaori-native-dialog' in template
    assert 'aria-labelledby="bulk-tls-rotation-confirm-title"' in template
    assert 'aria-describedby="bulk-tls-rotation-confirm-description"' in template
    assert 'data-kaori-dialog-close' in template
    assert 'selectedTargets: []' in template
    assert "document.querySelectorAll('input[name=certificate_ids]:checked')" in template
    assert 'x-for="target in selectedTargets.slice(0, 3)"' in template
    assert 'x-text="selectedCount - 3"' in template
    assert 'Existing TLS material will be replaced' in template
    assert 'no automatic rollback.' in template
    assert 'action_button.classes(\'secondary\')' in template
    assert 'action_button.classes(\'primary\')' in template
    assert '@htmx:before-request="$refs.bulkConfirmDialog?.close()"' in template
    assert 'updateModal' not in template
    assert 'x-show="updateModal"' not in template


def test_bulk_tls_confirmation_explanations_are_compact_on_desktop() -> None:
    template = _template()
    dialog = template.split('<dialog id="bulk-tls-rotation-confirm-dialog"', 1)[1].split('</dialog>', 1)[0]

    assert 'Apply the validated TLS pair to the selected Secrets.' in dialog
    assert 'Replaces <span class="font-semibold">tls.crt</span> and <span class="font-semibold">tls.key</span>; no automatic rollback.' in dialog
    assert 'KAORI rechecks the pair, coverage, and target identity.' in dialog
    # Desktop keeps the three selected notes on one line; mobile may wrap.
    assert dialog.count('sm:whitespace-nowrap') == 3


def test_tls_rotation_file_names_can_wrap_without_truncation() -> None:
    template = _template()
    assert 'x-text="crtFileName"' in template
    assert 'x-text="keyFileName"' in template
    assert 'break-words text-xs font-medium text-content-secondary [overflow-wrap:anywhere]' in template
    assert 'truncate text-sm font-medium text-content-secondary' not in template


def test_single_tls_rotation_page_surfaces_current_tls_posture() -> None:
    template = _rotate_template()
    assert 'Current TLS Posture' in template
    assert 'Committed validity and host coverage' in template
    assert 'Expires At' in template
    assert 'Days Remaining' in template
    assert 'Host Coverage' in template
    assert 'Fingerprint' in template
    assert "table_label.status_label(record.presentation.status_label or 'Unknown'" in template


def test_single_tls_rotation_validation_is_embedded_with_upload_pair() -> None:
    template = _rotate_template()
    assert 'Replacement Certificate Pair & Validation' in template
    assert "secret_ui.action_bar('shield-check', 'Validate Before Update'" in template
    assert 'embedded=true' in template
    assert 'id="tls-secret-rotate-validation-result"' in template
    assert 'context_rail.html' not in template
