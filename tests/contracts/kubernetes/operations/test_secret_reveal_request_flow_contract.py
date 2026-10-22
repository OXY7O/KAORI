from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_new_request_keeps_step_up_out_of_request_creation() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')

    new_panel = page.split('data-secret-reveal-panel="new"', 1)[1].split('data-secret-reveal-panel="mine"', 1)[0]
    mine_panel = page.split('data-secret-reveal-panel="mine"', 1)[1]

    assert 'Reveal Session Step-Up' not in new_panel
    assert '_reveal_step_up.html' in mine_panel
    assert 'Verify your session before consuming an approved request.' in step_up
    assert 'Approval, identity and single-use access remain separate controls.' in step_up


def test_request_form_explains_policy_specific_next_step() -> None:
    request_form = read('app/templates/kubernetes/operations/secrets/_reveal_request_form.html')

    assert "selected_namespace_policy == 'approval_required'" in request_form
    assert "table_label.status_label('Approval Required'" in request_form
    assert "table_label.status_label('Step-Up Policy'" in request_form
    assert 'wait for an independent approver' in request_form
    assert 'verify the current KAORI session' in request_form


def test_protected_reveal_flow_matches_backend_policy_order() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    service = read('app/kubernetes/operations/secrets/reveal_service.py')

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
    request_status = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')

    assert "url_for('kubernetes_operations.reveal_secret', reveal_view='mine', _anchor='reveal-session-step-up')" in request_status
    assert 'data-reveal-step-up-trigger' in request_status
    assert 'Verify Session' in request_status
    assert 'Reauthenticate first' not in request_status


def test_one_time_reveal_locks_only_the_request_row() -> None:
    service = read('app/kubernetes/operations/secrets/reveal_service.py')

    assert 'query.enable_eagerloads(False).with_for_update(of=SecretRevealRequest)' in service
    assert 'query = query.with_for_update()' not in service
    assert 'lock_for_update=True' in service


def test_reveal_step_up_keeps_password_and_action_on_one_control_baseline() -> None:
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')

    assert 'components/form_field.html' in step_up
    assert 'data-reveal-step-up-workspace' in step_up
    assert 'form_field.label_row(' in step_up and 'Current KAORI Password' in step_up
    assert 'class="{{ form_field.input_classes() }}"' in step_up
    assert "action_button.classes('primary')" in step_up
    assert 'name="password"' in step_up
    assert 'name="csrf_token"' in step_up
    assert 'current_user.is_external' in step_up



def test_verify_session_action_focuses_password_after_htmx_table_replacement() -> None:
    table = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    js = read('app/static/js/secret_reveal_workspace.js')
    browser = read('tests/ui/test_browser_smoke.py')

    assert "item.status == 'approved'" in table
    assert '{% elif can_reveal %}' in table
    assert 'data-reveal-step-up-trigger' in table
    assert "reveal_view='mine', _anchor='reveal-session-step-up'" in table
    assert 'Reveal access unavailable' in table
    assert 'id="reveal-session-step-up"' in step_up
    assert 'tabindex="-1"' in step_up
    assert 'data-reveal-step-up-password' in step_up
    assert 'name="password"' in step_up
    assert 'name="csrf_token"' in step_up

    # Delegate after HTMX swaps rather than attaching handlers to replaced rows.
    assert "document.addEventListener('click', navigateToStepUp)" in js
    assert "event.target.closest(stepUpTriggerSelector)" in js
    assert "link.closest(rootSelector)" in js
    assert "querySelector('#reveal-session-step-up')" in js
    assert "querySelector('[data-reveal-step-up-password]')" in js
    assert "target.closest('[data-kaori-main-scroll]')" in js
    assert "bounds.top >= viewport.top + padding && bounds.bottom <= viewport.bottom - padding) return" in js
    assert "Math.min(limit, main.scrollTop + bounds.top - viewport.top - padding)" in js
    assert "main.scrollTo({ top: next, behavior: 'auto' })" in js
    assert "target.scrollIntoView({ behavior: 'auto', block: 'nearest' })" in js
    assert "behavior: 'smooth'" not in js
    assert "focusTarget.focus({ preventScroll: true })" in js
    assert "url.searchParams.set('reveal_view', 'mine')" in js
    assert "window.history.replaceState(window.history.state, '', url)" in js
    assert "if (!target || !panel || panel.hidden) return" in js
    assert "window.htmx.ajax('GET', url, { target, swap: 'outerHTML' })" in js
    assert "test_verify_session_link_focuses_step_up_after_htmx_replacement" in browser


def test_verify_session_scroll_stays_in_kaori_main_viewport() -> None:
    js = read('app/static/js/secret_reveal_workspace.js')
    layout = read('app/templates/layouts/app.html')
    browser = read('tests/ui/test_browser_smoke.py')

    assert 'data-kaori-main-scroll' in layout
    assert "target.closest('[data-kaori-main-scroll]')" in js
    assert "if (bounds.top >= viewport.top + padding && bounds.bottom <= viewport.bottom - padding) return" in js
    assert "const limit = Math.max(0, main.scrollHeight - main.clientHeight)" in js
    assert "Math.max(0, Math.min(limit," in js
    assert "main.scrollTo({ top: next, behavior: 'auto' })" in js
    assert "target.scrollIntoView({ behavior: 'auto', block: 'nearest' })" in js
    assert "focusTarget.focus({ preventScroll: true })" in js
    assert "behavior: 'smooth'" not in js
    assert "test_verify_session_does_not_overscroll_kaori_main_viewport" in browser
