from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/kubernetes_operations/secrets/tls_rotation.html'


def _template() -> str:
    return TEMPLATE.read_text()


def test_tls_rotation_uses_one_primary_workspace() -> None:
    template = _template()

    assert 'Controlled TLS Rotation Flow' in template
    assert 'Validate Before Bulk Rotation' in template
    assert 'id="tls-secret-update-form"' in template
    assert 'info_flow.render' not in template
    assert '<aside' not in template
    assert '<details' not in template
    assert '<summary' not in template
    assert 'xl:grid-cols-3' in template
    assert 'xl:col-span-2' in template
    assert 'xl:col-span-1' in template


def test_tls_rotation_actions_are_inside_the_primary_form() -> None:
    template = _template()
    form_start = template.index('id="tls-secret-update-form"')
    form_end = template.index('</form>', form_start)
    form = template[form_start:form_end]

    assert 'Validate Selected' in form
    assert 'Update Selected' in form
    assert 'border-t border-outline-default bg-surface-hover' in form
    assert 'Security Note' in form
    assert 'Validation Required Before Update' in form


def test_tls_rotation_file_names_can_wrap_without_truncation() -> None:
    template = _template()

    assert 'x-text="crtFileName"' in template
    assert 'x-text="keyFileName"' in template
    assert 'break-all text-sm font-medium text-content-secondary' in template
    assert 'truncate text-sm font-medium text-content-secondary' not in template
