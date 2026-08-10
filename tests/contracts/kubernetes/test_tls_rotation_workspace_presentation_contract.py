from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/kubernetes_operations/secrets/tls_rotation.html'
ROTATE_TEMPLATE = ROOT / 'app/templates/kubernetes_operations/secrets/tls_rotate.html'


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
