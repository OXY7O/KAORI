from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_form_field_owns_target_alignment_geometry() -> None:
    source = read('app/templates/components/form_field.html')
    assert 'min-h-6' in source
    assert 'mt-2 box-border h-10 min-h-10 w-full' in source
    assert 'components/table_label.html' in source
    assert 'help(text)' in source


def test_configmap_and_secret_target_rows_use_shared_form_field_contract() -> None:
    consumers = (
        'app/templates/kubernetes/operations/configmaps/create.html',
        'app/templates/kubernetes/operations/configmaps/_namespace_options.html',
        'app/templates/kubernetes/operations/configmaps/_workspace.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/_namespace_field.html',
        'app/templates/kubernetes/operations/secrets/replace.html',
        'app/templates/kubernetes/operations/secrets/_replace_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/delete.html',
        'app/templates/kubernetes/operations/secrets/_delete_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/reveal.html',
        'app/templates/kubernetes/operations/secrets/_reveal_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/_reveal_step_up.html',
    )
    for relative in consumers:
        assert 'components/form_field.html' in read(relative), relative

    secret_create = read('app/templates/kubernetes/operations/secrets/create.html')
    assert 'components/info_tip.html' in secret_create
    assert 'secret-create-name-tip' in secret_create and 'Use a DNS-compatible Kubernetes resource name.' in secret_create
    assert 'secret-create-mutability-tip' in secret_create and 'Mutable permits future governed updates' in secret_create
    assert 'form_field.help("DNS-compatible resource name")' not in secret_create
    assert 'form_field.help("Control future updates")' not in secret_create


def test_secret_replace_actions_live_in_htmx_swapped_target_content() -> None:
    page = read('app/templates/kubernetes/operations/secrets/replace.html')
    partial = read('app/templates/kubernetes/operations/secrets/_replace_content_form.html')
    assert '{% if target and not target.immutable %}' not in page
    assert 'replace-secret-apply-button' in partial
    assert 'Validate Replacement' in partial
    assert 'Replace Selected Data' in partial
    assert 'Current Values Stay Hidden' in partial
    assert 'embedded=true' in partial


def test_secret_reveal_step_up_aligns_password_and_verify_action() -> None:
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')

    assert 'sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end' in step_up
    assert 'form_field.label_row(' in step_up and 'Current KAORI Password' in step_up
    assert 'class="{{ form_field.input_classes() }}"' in step_up
    assert (
        'form_field.help(' in step_up
        and 'Step-up is required only before consuming an approved reveal request.' in step_up
    )

def test_operations_move_routine_field_guidance_to_info_tips_but_keep_required_state_visible() -> None:
    reviewed = (
        'app/templates/kubernetes/operations/configmaps/create.html',
        'app/templates/kubernetes/operations/configmaps/_namespace_options.html',
        'app/templates/kubernetes/operations/configmaps/_workspace.html',
        'app/templates/kubernetes/operations/configmaps/_editor.html',
        'app/templates/kubernetes/operations/secrets/create.html',
        'app/templates/kubernetes/operations/secrets/_namespace_field.html',
        'app/templates/kubernetes/operations/secrets/replace.html',
        'app/templates/kubernetes/operations/secrets/delete.html',
        'app/templates/kubernetes/operations/secrets/reveal.html',
        'app/templates/kubernetes/operations/secrets/_replace_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/_delete_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/_reveal_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/_replace_content_form.html',
    )
    for relative in reviewed:
        assert 'components/info_tip.html' in read(relative), relative

    combined = '\n'.join(read(relative) for relative in reviewed)
    for retired_helper in (
        'form_field.help("Registered cluster for the target namespace.")',
        'form_field.help("Loaded from the selected Kubernetes API.")',
        'form_field.help("DNS-compatible resource name")',
        'form_field.help("Control future updates")',
        'Target identity and type come from live Kubernetes.</span>',
        'Merge preserves unsubmitted keys. Replace removes keys omitted from this form.</p>',
        'Leave blank to keep the current username.</span>',
    ):
        assert retired_helper not in combined

    # Required operational state remains persistent, never tooltip-only.
    assert 'No live namespace is available for the selected cluster.' in combined
    assert 'No ConfigMap currently exists in this live namespace.' in combined
    assert 'No supported live Secret was found in this namespace.' in combined
    assert 'No revealable live Opaque, Basic Auth, or Registry Secret was found.' in combined

    delete_configmap = read('app/templates/kubernetes/operations/configmaps/_delete_target.html')
    delete_secret = read('app/templates/kubernetes/operations/secrets/_delete_target.html')
    reveal_request = read('app/templates/kubernetes/operations/secrets/_reveal_request_form.html')
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    assert 'must exactly match the selected live ConfigMap name' in delete_configmap
    assert 'must exactly match the selected live Secret name' in delete_secret
    assert 'TLS private keys and SSH private keys are never revealable.' in reveal_request
    assert 'Step-up is required only before consuming an approved reveal request.' in step_up

