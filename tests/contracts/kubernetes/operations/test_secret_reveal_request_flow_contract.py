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
    assert 'KAORI records request details, not Secret values.' in request_form
    assert 'Verify and reveal once in My Requests after approval.' in request_form


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

    assert "item.effective_status == 'approved'" in table
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


def test_approved_request_cta_uses_bounded_focused_navigation_instead_of_native_hash_scroll() -> None:
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    requests = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    workspace_js = read('app/static/js/secret_reveal_workspace.js')
    browser = read('tests/ui/test_browser_smoke.py')

    assert 'data-reveal-approved-requests-trigger' in step_up
    assert 'href="#my-secret-reveal-requests"' in step_up  # no-JS fallback
    assert 'tabindex="-1"' in requests
    assert 'id="my-secret-reveal-requests"' in requests
    assert 'data-reveal-once-action' in requests
    assert 'class="{{ table_ui.action_classes() }}"' in requests
    assert "const approvedRequestsTriggerSelector = '[data-reveal-approved-requests-trigger]'" in workspace_js
    assert "document.addEventListener('click', navigateToApprovedRequest)" in workspace_js
    assert "event.target.closest(approvedRequestsTriggerSelector)" in workspace_js
    assert "panel.querySelector('[data-reveal-once-action]')" in workspace_js
    assert "panel.querySelector('#my-secret-reveal-requests')" in workspace_js
    assert "event.preventDefault()" in workspace_js
    assert "showWithinMainScroll(target)" in workspace_js
    assert "target.focus({ preventScroll: true })" in workspace_js
    assert "window.history.replaceState(window.history.state, '', url)" in workspace_js
    assert "test_continue_to_approved_requests_scrolls_only_main_and_focuses_action" in browser


def test_requester_approval_notification_opens_exact_owned_request_and_preserves_step_up() -> None:
    routes = read('app/kubernetes/operations/secrets/reveal_routes.py')
    service = read('app/kubernetes/operations/secrets/reveal_service.py')
    table = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    docs = read('app/kubernetes/operations/secrets/README.md')

    # The notification targets one committed request; no native registry fragment.
    decision = routes.split('def decide_secret_reveal_request(', 1)[1]
    requester_notification = decision.split('create_notification(', 1)[1].split(
        'metadata=_reveal_request_metadata(record)', 1
    )[0]
    assert "my_request_id=record.id" in requester_notification
    assert "_anchor='my-secret-reveal-requests'" not in requester_notification
    assert "my_request_id=request.args.get('my_request_id', '')" in routes

    # Ownership is a prerequisite to exact request selection, not a fallback.
    assert 'my_request_id: str = \'\'' in service
    assert 'SecretRevealRequest.query.filter_by(requester_user_id=user_id)' in service
    assert 'my_query = my_query.filter(SecretRevealRequest.id == focus_id)' in service
    assert service.index('query.filter_by(requester_user_id=user_id)') < service.index(
        'SecretRevealRequest.id == focus_id'
    )
    assert "'my_reveal_focus_id': focus_id" in service
    assert 'my_request_id=my_reveal_focus_id' in table
    assert "'my_request_id': my_reveal_focus_id" in table

    # No extra reveal endpoint; existing guarded row action is authoritative.
    assert 'Request Approved · Ready for Reveal' in table
    assert 'Show All Requests' in table
    assert 'Request Not Available' in table
    assert 'linked_request.effective_status' in table
    assert 'data-reveal-once-action' in table
    assert 'hx-target="#reveal-value-output"' in table
    assert 'name="csrf_token"' in table
    assert 'name="my_request_id"' in step_up
    assert 'value="{{ my_reveal_focus_id }}"' in step_up
    assert 'A request from your notification is selected below.' in step_up
    assert "linked_request_id = (request.form.get('my_request_id') or '').strip()" in routes
    assert "if len(linked_request_id) > 80:" in routes
    assert 'return redirect(return_url)' in routes
    assert '**Requester decision deep links:**' in docs


def test_one_time_reveal_consumption_is_commit_coupled_to_activity_evidence() -> None:
    source = read('app/kubernetes/operations/secrets/reveal_service.py')
    routes = read('app/kubernetes/operations/secrets/reveal_routes.py')
    activity = read('app/platform_operations/notifications/service.py')

    consume = source.split('def reveal_secret_value(request_id:', 1)[1]
    assert 'lock_for_update=True' in consume
    assert "record.status = 'revealed'" in consume
    assert 'audit_feedback = stage_operational_activity(' in consume
    assert "event_type='kubernetes_secret_revealed'" in consume
    assert 'delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY' in consume
    assert consume.index('audit_feedback = stage_operational_activity(') < consume.index('db.session.commit()')
    assert 'except Exception as exc:' in consume
    assert 'db.session.rollback()' in consume
    assert 'audit_feedback=audit_feedback' in consume
    reveal_route = routes.split('def reveal_secret_value(request_id:', 1)[1]
    assert 'audit_action_url=url_for(' in reveal_route
    assert 'feedback = result.audit_feedback' in reveal_route
    assert "_record_secret_activity(\n            event_type='kubernetes_secret_revealed'" not in reveal_route
    staged = activity.split('def stage_operational_activity(', 1)[1]
    assert 'commit=False' in staged
    assert 'policy = OperationalDeliveryPolicy.normalize(delivery_policy)' in staged
    assert 'deck_visible=policy.deck_visible(status)' in staged
