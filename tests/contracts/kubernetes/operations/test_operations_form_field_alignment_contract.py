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

    shared_ui = read('app/templates/components/kubernetes_operation_ui.html')
    secret_create = read('app/templates/kubernetes/operations/secrets/create.html')
    assert 'components/info_tip.html' in shared_ui
    assert 'info_id=None' in shared_ui and 'info_items=None' in shared_ui
    assert 'secret-create-guidance-tip' in secret_create
    assert 'Secret Name must be DNS-compatible.' in secret_create
    assert 'Mutable permits later governed replacement.' in secret_create
    assert 'secret-create-name-tip' not in secret_create
    assert 'secret-create-mutability-tip' not in secret_create
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

def test_operations_consolidate_routine_guidance_at_section_headers_but_keep_required_state_visible() -> None:
    header_owners = {
        'app/templates/kubernetes/operations/configmaps/create.html': 'configmap-create-guidance-tip',
        'app/templates/kubernetes/operations/configmaps/update.html': 'configmap-update-guidance-tip',
        'app/templates/kubernetes/operations/configmaps/delete.html': 'configmap-delete-guidance-tip',
        'app/templates/kubernetes/operations/secrets/create.html': 'secret-create-guidance-tip',
        'app/templates/kubernetes/operations/secrets/replace.html': 'secret-replace-target-guidance-tip',
        'app/templates/kubernetes/operations/secrets/delete.html': 'secret-delete-target-guidance-tip',
        'app/templates/kubernetes/operations/secrets/reveal.html': 'secret-reveal-target-guidance-tip',
        'app/templates/kubernetes/operations/secrets/_replace_content_form.html': 'secret-replace-content-guidance-tip',
    }
    for relative, guidance_id in header_owners.items():
        assert guidance_id in read(relative), relative

    field_partials = (
        'app/templates/kubernetes/operations/configmaps/_namespace_options.html',
        'app/templates/kubernetes/operations/configmaps/_workspace.html',
        'app/templates/kubernetes/operations/configmaps/_editor.html',
        'app/templates/kubernetes/operations/secrets/_namespace_field.html',
        'app/templates/kubernetes/operations/secrets/_replace_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/_delete_target_workspace.html',
        'app/templates/kubernetes/operations/secrets/_reveal_target_workspace.html',
    )
    for relative in field_partials:
        source = read(relative)
        assert 'info_tip.render' not in source, relative
        assert 'components/info_tip.html' not in source, relative

    reviewed = tuple(header_owners) + field_partials
    combined = '\n'.join(read(relative) for relative in reviewed)
    for retired_tip in (
        'configmap-create-cluster-tip',
        'configmap-create-namespace-tip',
        'configmap-create-name-tip',
        'configmap-target-cluster-tip',
        'configmap-target-namespace-tip',
        'configmap-target-object-tip',
        'configmap-update-mode-tip',
        'secret-create-cluster-tip',
        'secret-create-namespace-tip',
        'secret-create-name-tip',
        'secret-create-mutability-tip',
        'secret-replace-cluster-tip',
        'secret-replace-target-namespace-tip',
        'secret-replace-target-secret-tip',
        'secret-delete-cluster-tip',
        'secret-delete-target-namespace-tip',
        'secret-delete-target-secret-tip',
        'secret-reveal-cluster-tip',
        'secret-reveal-target-namespace-tip',
        'secret-reveal-target-secret-tip',
        'secret-replace-basic-username-tip',
    ):
        assert retired_tip not in combined

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

