from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_new_request_keeps_step_up_out_of_request_creation() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    step_up = read('app/templates/kubernetes_operations/secrets/_reveal_step_up.html')

    new_panel = page.split('data-secret-reveal-panel="new"', 1)[1].split('data-secret-reveal-panel="mine"', 1)[0]
    mine_panel = page.split('data-secret-reveal-panel="mine"', 1)[1]

    assert 'Reveal Session Step-Up' not in new_panel
    assert '_reveal_step_up.html' in mine_panel
    assert 'Verify identity only when an approved request is ready to be consumed.' in step_up
    assert 'Step-up is required only before consuming an approved reveal request.' in step_up


def test_request_form_explains_policy_specific_next_step() -> None:
    request_form = read('app/templates/kubernetes_operations/secrets/_reveal_request_form.html')

    assert "selected_namespace_policy == 'approval_required'" in request_form
    assert "table_label.status_label('Approval Required'" in request_form
    assert "table_label.status_label('Step-Up Policy'" in request_form
    assert 'wait for an independent approver' in request_form
    assert 'verify the current KAORI session' in request_form


def test_protected_reveal_flow_matches_backend_policy_order() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    service = read('app/kubernetes_operations/secrets/reveal_service.py')

    assert "('Choose Target'," in page
    assert "('Submit Context'," in page
    assert "('Resolve Policy'," in page
    assert "('Verify Identity'," in page
    assert "('Reveal Once'," in page

    assert "if namespace_policy == 'approval_required':" in service
    assert "elif namespace_policy == 'step_up':" in service
    assert "status = 'pending'" in service
    assert "status = 'approved'" in service


def test_approved_request_links_back_to_step_up_when_session_is_not_verified() -> None:
    request_status = read('app/templates/kubernetes_operations/secrets/_reveal_request_status.html')

    assert 'href="#reveal-session-step-up"' in request_status
    assert 'Verify Session' in request_status
    assert 'Reauthenticate first' not in request_status


def test_one_time_reveal_locks_only_the_request_row() -> None:
    service = read('app/kubernetes_operations/secrets/reveal_service.py')

    assert 'query.enable_eagerloads(False).with_for_update(of=SecretRevealRequest)' in service
    assert 'query = query.with_for_update()' not in service
    assert 'lock_for_update=True' in service


def test_reveal_step_up_keeps_password_and_action_on_one_control_baseline() -> None:
    step_up = read('app/templates/kubernetes_operations/secrets/_reveal_step_up.html')

    assert 'components/form_field.html' in step_up
    assert 'sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end' in step_up
    assert 'form_field.label_row(' in step_up and 'Current KAORI Password' in step_up
    assert 'class="{{ form_field.input_classes() }}"' in step_up
    assert 'form_field.help(' in step_up and 'Step-up is required only before consuming an approved reveal request.' in step_up
