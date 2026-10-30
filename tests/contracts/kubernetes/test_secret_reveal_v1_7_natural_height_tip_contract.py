from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_global_gate_guidance_uses_compact_activation_tip() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')

    assert 'Activation Tip' in page
    assert (
        'Policy-enabled Namespace configuration is ready, but target selection is locked by the global kill switch.'
        in page
    )
    assert 'KUBERNETES_SECRET_REVEAL_ENABLED=true' in page
    assert 'restart KAORI' in page
    assert '<span class="mt-1.5 block text-xs leading-5 text-status-warning-text">' not in page


def test_protected_reveal_new_request_uses_form_with_right_context() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    assert 'data-kubernetes-operation-layout="form-context-v1"' in page
    assert 'components/form_with_context_rail.html' in page
    assert 'form_context.layout_classes()' in page
    assert 'form_context.main_classes()' in page
    assert 'form_context.rail_classes()' in page
    assert "context_rail.layout_classes('wide')" not in page
    assert 'context_rail.rail_classes()' not in page
    assert 'Protected Reveal Flow' in page
    assert 'Reveal Safety Contract' in page
    assert 'secret_ui.workflow_control(' not in page


def test_administration_readiness_and_boundary_cards_use_content_height() -> None:
    page = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    readiness_grid = (
        'mt-4 grid min-w-0 overflow-hidden rounded-xl border border-outline-subtle '
        'bg-surface-card sm:grid-cols-2 lg:grid-cols-3'
    )
    assert readiness_grid in page
    assert 'grid items-stretch gap-4' not in page
    assert 'h-full overflow-hidden rounded-2xl' not in page
    assert 'flex h-full flex-col overflow-hidden rounded-2xl' not in page
    assert 'grid flex-1 gap-3' not in page
    assert page.count('flex min-w-0 flex-col gap-3') >= 3
    assert 'Cluster Credential' in page
    assert 'Encryption at Rest' in page
    assert 'Metadata Audit' in page


def test_secret_reveal_v17_keeps_neutral_dark_mode_surfaces() -> None:
    protected = read('app/templates/kubernetes/operations/secrets/reveal.html')
    administration = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    for source in (protected, administration):
        assert 'bg-white' not in source
    assert 'bg-surface-card' in protected
    assert 'bg-surface-card' in administration


def test_review7_reveal_step_up_uses_one_compact_responsive_panel() -> None:
    step = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    assert 'data-reveal-step-up-workspace' in step
    assert 'grid min-w-0 gap-0 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]' in step
    assert step.count('secret_ui.section_header(') == 1
    assert 'aria-label="Step-Up Access Guidance"' in step
    assert 'Approved Request' in step
    assert 'Verified Session' in step
    assert 'One-Time Reveal' in step
    assert 'name="password"' in step
    assert 'name="csrf_token"' in step
    assert 'current_user.is_external' in step
    assert 'Protected Session Verified' in step


def test_reveal_step_up_uses_shared_button_and_source_driven_session_context() -> None:
    step = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    shared_button = read('app/templates/components/action_button.html')
    shared_labels = read('app/templates/components/table_label.html')

    assert 'components/action_button.html' in step
    assert "action_button.classes('primary')" in step
    assert 'macro classes(variant=' in shared_button
    assert 'components/table_label.html' in step
    assert 'table_label.status_indicator_label(' in step
    assert 'macro status_indicator_label(' in shared_labels
    assert 'Session Verification' in step
    assert 'Verification Required' in step
    assert 'Approval, identity and single-use access remain separate controls.' in step
    assert '<ol class="mt-4 grid min-w-0 gap-3">' in step
    assert 'Expiry, policy, authorization and audit still apply.' in step
    assert 'name="password"' in step
    assert 'autocomplete="current-password"' in step
    assert 'name="csrf_token"' in step
    assert 'current_user.is_external' in step
    assert 'step_up_active' in step
    assert 'aria-label="Reveal Session Step-Up and access guidance"' in step
    assert 'data-reveal-step-up-workspace' in step


def test_review7_reveal_target_empty_cluster_status_not_below_form() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    assert 'No eligible protected cluster' in page
    assert 'No eligible cluster. Review readiness or policy.' not in page
    assert 'KUBERNETES_SECRET_REVEAL_ENABLED=true' in page
    assert 'selection_error' in page
    assert "info_id='secret-reveal-target-guidance-tip'" in page


def test_review7_reveal_guidance_copy_stays_compact() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    # Preserve policy semantics while fitting each guidance sentence on one
    # line where the existing context rail has sufficient width.
    for copy in (
        'Approval and step-up follow Namespace policy.',
        'My Requests: track, step up, reveal once.',
        'Safeguards apply through one-time reveal.',
        'TLS/SSH private keys cannot be revealed.',
        'Requesters cannot approve their own requests.',
        'Step up before using an approved request.',
        'Audit records context, never secret values.',
    ):
        assert copy in page

    assert 'No eligible cluster. Review readiness or policy.' not in page
    assert 'No eligible protected cluster' in page
    assert "info_id='secret-reveal-target-guidance-tip'" in page
    assert 'selection_error' in page


def test_review8_reveal_target_horizontal_alignment_uses_shared_fields() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    workspace = read('app/templates/kubernetes/operations/secrets/_reveal_target_workspace.html')
    form_field = read('app/templates/components/form_field.html')

    # Each of three horizontally adjacent fields reserves the same label-row
    # height, even though only Secret displays a Live status badge.
    assert '{{ form_field.label_row("Cluster") }}' in page
    assert '{{ form_field.label_row("Namespace") }}' in workspace
    assert "{{ form_field.label_row('Secret', 'Live', 'normal', 'radio') }}" in workspace
    assert 'flex min-h-6 items-center justify-between gap-2' in form_field
    assert 'table_label.status_label(status_text, status_tone, status_icon)' in form_field

    # Use the same select height, padding, focus ring, and disabled state.
    assert 'class="{{ form_field.select_classes() }}"' in page
    assert workspace.count('class="{{ form_field.select_classes() }}"') == 2
    assert 'mt-2 box-border h-10 min-h-10 w-full' in form_field
    assert 'class="grid gap-5 lg:grid-cols-3"' in page

    # Preserve the HTMX replacement boundary, live evidence, and safe states.
    assert 'id="reveal-target-workspace" class="contents"' in workspace
    assert 'hx-swap-oob="outerHTML"' in workspace
    assert 'No eligible protected cluster' in page
    assert 'selection_error' in page
    assert "info_id='secret-reveal-target-guidance-tip'" in page
