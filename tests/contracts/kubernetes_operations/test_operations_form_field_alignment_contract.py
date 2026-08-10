from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_form_field_owns_target_alignment_geometry() -> None:
    source = read('app/templates/components/form_field.html')
    assert 'min-h-6' in source
    assert 'mt-2 h-10 w-full' in source
    assert 'components/table_label.html' in source
    assert 'help(text)' in source


def test_configmap_and_secret_target_rows_use_shared_form_field_contract() -> None:
    consumers = (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/_namespace_options.html',
        'app/templates/kubernetes_operations/configmaps/_workspace.html',
        'app/templates/kubernetes_operations/secrets/create.html',
        'app/templates/kubernetes_operations/secrets/_namespace_field.html',
        'app/templates/kubernetes_operations/secrets/replace.html',
        'app/templates/kubernetes_operations/secrets/_replace_target_workspace.html',
        'app/templates/kubernetes_operations/secrets/delete.html',
        'app/templates/kubernetes_operations/secrets/_delete_target_workspace.html',
        'app/templates/kubernetes_operations/secrets/reveal.html',
        'app/templates/kubernetes_operations/secrets/_reveal_target_workspace.html',
    )
    for relative in consumers:
        assert 'components/form_field.html' in read(relative), relative

    secret_create = read('app/templates/kubernetes_operations/secrets/create.html')
    assert "form_field.help('DNS-compatible resource name')" in secret_create
    assert "form_field.help('Control future updates')" in secret_create
    assert 'DNS-compatible resource name</span>\n                        <input' not in secret_create


def test_secret_replace_actions_live_in_htmx_swapped_target_content() -> None:
    page = read('app/templates/kubernetes_operations/secrets/replace.html')
    partial = read('app/templates/kubernetes_operations/secrets/_replace_content_form.html')
    assert '{% if target and not target.immutable %}' not in page
    assert 'replace-secret-apply-button' in partial
    assert 'Validate Replacement' in partial
    assert 'Replace Selected Data' in partial
    assert 'Current Values Stay Hidden' in partial
    assert 'embedded=true' in partial
