from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_protected_reveal_templates_compile_with_jinja() -> None:
    """Fail fast on malformed Jinja delimiters, including hidden workspace tabs."""
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=True)
    env.filters['user_datetime'] = str
    for relative in (
        'kubernetes/operations/secrets/reveal.html',
        'kubernetes/operations/secrets/_reveal_request_form.html',
        'kubernetes/operations/secrets/_reveal_step_up.html',
        'kubernetes/operations/secrets/_reveal_request_status.html',
        'kubernetes/operations/secrets/_reveal_pending_approvals.html',
        'kubernetes/operations/secrets/_reveal_value.html',
    ):
        env.get_template(relative)

    source = read('app/templates/kubernetes/operations/secrets/reveal.html')
    assert '{% include "kubernetes/operations/secrets/_reveal_request_status.html" %}' in source
    assert '{% include "kubernetes/operations/secrets/_reveal_request_status.html" %>' not in source


def test_protected_reveal_uses_analytics_content_tab_treatment() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    tabs = read('app/templates/components/content_tabs.html')

    assert 'components/content_tabs.html' in page
    assert 'content_tabs.render_controlled_links' in page
    assert "reveal_view='new'" in page
    assert "reveal_view='mine'" in page
    assert 'data-kaori-tab-fallback="server-navigation"' in tabs
    assert 'components/segmented_tabs.html' not in page
    assert 'data-kaori-tab-variant="content-tabs-controlled"' in tabs
    assert 'data-kaori-tab-control="alpine-url-fallback"' in tabs
    assert "('new', 'New Request'" in page
    assert "('mine', 'My Requests'" in page
    assert "('approvals', 'Approvals'" in page
    assert "('mine', 'My Requests', 'history', none," in page
    assert "('approvals', 'Approvals', 'user-check', none," in page
    assert "('mine', 'My Requests', 'history', my_reveal_pagination.total" not in page
    assert "('approvals', 'Approvals', 'user-check', pending_reveal_pagination.total" not in page


def test_reveal_tab_state_uses_canonical_alpine_workspace_controller() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    routes = read('app/kubernetes/operations/secrets/reveal_routes.py')

    assert "'active_reveal_view': active_reveal_view" in routes
    assert "request.args.get('reveal_view')" in routes
    assert "activeTab: '{{ active_reveal_view }}'" in page
    assert 'setTab(tab)' in page
    assert "url.searchParams.set('reveal_view', tab)" in page
    assert 'window.history.replaceState' in page
    assert '#my-secret-reveal-requests' in page and "'mine'" in page
    assert '#pending-secret-reveal-approvals' in page and "'approvals'" in page


def test_reveal_tabs_switch_client_side_with_server_navigation_fallback() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    tabs = read('app/templates/components/content_tabs.html')

    assert '@click.prevent="setTab(' in tabs
    assert 'href="{{ tab_href }}"' in tabs
    assert 'data-kaori-tab-fallback="server-navigation"' in tabs
    assert "reveal_view='new'" in page
    assert "reveal_view='mine'" in page
    assert 'x-show="activeTab === \'new\'"' in page
    assert 'x-show="activeTab === \'mine\'"' in page
    assert 'x-bind:hidden="activeTab !== \'new\'"' in page
    assert 'x-bind:hidden="activeTab !== \'mine\'"' in page


def test_reveal_safety_contract_is_collapsed_by_default() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')

    assert "information_guide_card.render('Reveal Safety Contract'" in page
    assert "protected_reveal_guardrails, icon='shield-check', open_by_default=false" in page


def test_reveal_redirects_preserve_the_next_workspace_view() -> None:
    routes = read('app/kubernetes/operations/secrets/reveal_routes.py')

    assert "reveal_view='mine'" in routes
    assert "_anchor='my-secret-reveal-requests'" in routes
    assert "reveal_view='approvals'" in routes
    assert "_anchor='pending-secret-reveal-approvals'" in routes


def test_reveal_polling_only_runs_for_the_active_replaceable_panel() -> None:
    script = read('app/static/js/secret_reveal_workspace.js')
    request_status = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    approvals = read('app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html')

    assert 'const activePanel = (root) =>' in script
    assert '!panel.hidden' in script
    assert "querySelector('[data-reveal-poll-owner]')" in script
    assert 'window.setInterval' in script
    assert 'secret-reveal:tab-changed' in script
    assert 'data-reveal-poll-owner' in request_status
    assert 'data-reveal-poll-owner' in approvals
    assert 'hx-trigger="every 4s"' not in request_status
    assert 'hx-trigger="every 4s"' not in approvals


def test_reveal_pagination_is_scoped_to_its_partial_owner() -> None:
    request_status = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    approvals = read('app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html')

    assert "'kubernetes_operations.reveal_secret_status'" in request_status
    assert 'data-reveal-poll-target="#secret-reveal-request-status"' in request_status
    assert "table_registry.footer('kubernetes_operations.reveal_secret'" in request_status
    assert "'kubernetes_operations.reveal_secret_approvals'" in approvals
    assert 'data-reveal-poll-target="#pending-secret-reveal-approvals"' in approvals
    assert "'pending-secret-reveal-approvals'," in approvals
    assert "page_param='pending_page'" in approvals
    assert "per_page_param='pending_per_page'" in approvals


def test_one_time_value_uses_protected_value_panel_and_clearing_script() -> None:
    partial = read('app/templates/kubernetes/operations/secrets/_reveal_value.html')
    panel = read('app/templates/components/protected_value_panel.html')
    script = read('app/static/js/secret_reveal_value.js')

    assert 'components/protected_value_panel.html' in partial
    assert 'data-protected-value-panel' in panel
    assert 'data-protected-value-countdown' in panel
    assert 'visibilitychange' in script
    assert 'pagehide' in script
    assert 'htmx:beforeSwap' in script
    assert 'clipboard' not in panel.lower()


def test_one_time_result_is_rendered_only_in_my_requests() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    registry = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    workspace_js = read('app/static/js/secret_reveal_workspace.js')
    value_js = read('app/static/js/secret_reveal_value.js')
    result = read('app/templates/kubernetes/operations/secrets/_reveal_value.html')
    route = read('app/kubernetes/operations/secrets/reveal_routes.py')

    new_panel = page.split('data-secret-reveal-panel="new"', 1)[1].split('data-secret-reveal-panel="mine"', 1)[0]
    my_panel = page.split('data-secret-reveal-panel="mine"', 1)[1].split('data-secret-reveal-panel="approvals"', 1)[0]
    assert 'id="reveal-value-output"' not in new_panel
    assert my_panel.count('id="reveal-value-output"') == 1
    assert (
        my_panel.index('_reveal_step_up.html')
        < my_panel.index('id="reveal-value-output"')
        < my_panel.index('_reveal_request_status.html')
    )
    assert 'hx-history="false"' in my_panel
    assert 'aria-label="One-Time Secret Reveal Result"' in my_panel
    assert 'tabindex="-1"' in my_panel
    assert 'aria-live="polite"' not in my_panel
    assert 'hx-target="#reveal-value-output"' in registry
    assert 'hx-post="{{ url_for(' in registry
    assert 'name="csrf_token"' in registry
    assert "item.effective_status == 'approved'" in registry
    assert 'step_up_active' in registry
    assert 'Continue to Approved Requests' in step_up
    assert 'href="#my-secret-reveal-requests"' in step_up
    assert 'Protected Session Verified' in step_up
    assert 'Session verified. Select Reveal Once on an approved request below.' in step_up

    # Navigation and reveal output remain inside the requester workspace.
    assert "document.addEventListener('htmx:afterSwap', focusRevealResult)" in workspace_js
    assert "result?.id !== 'reveal-value-output'" in workspace_js
    assert 'if (!result.firstElementChild) return' in workspace_js
    assert 'showWithinMainScroll(result)' in workspace_js
    assert 'result.focus({ preventScroll: true })' in workspace_js
    assert "window.addEventListener('secret-reveal:tab-changed'" in value_js
    assert "if (event.detail?.tab === 'mine') return" in value_js
    assert 'visibilitychange' in value_js and 'pagehide' in value_js
    assert 'htmx:beforeSwap' in value_js
    assert 'components/protected_value_panel.html' in result
    assert 'render_template(' in route and "'kubernetes/operations/secrets/_reveal_value.html'" in route
    assert "response.headers['Cache-Control'] = 'no-store, private, max-age=0'" in route
    assert "response.headers['Referrer-Policy'] = 'no-referrer'" in route
    assert "response.headers['X-Content-Type-Options'] = 'nosniff'" in route


def test_reveal_tab_labels_are_count_free_but_registry_counts_remain() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    my = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    pending = read('app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html')
    assert "('new', 'New Request', 'key-round', none," in page
    assert "('mine', 'My Requests', 'history', none," in page
    assert "('approvals', 'Approvals', 'user-check', none," in page
    assert 'result_count=my_reveal_pagination.total_items' in my
    assert 'result_count=pending_reveal_pagination.total_items' in pending


def test_secret_reveal_submit_uses_tab_selection_without_native_registry_anchor() -> None:
    route = read('app/kubernetes/operations/secrets/reveal_routes.py')
    start = route.index('def request_secret_reveal():')
    end = route.index('def reauthenticate_secret_reveal():', start)
    block = route[start:end]

    assert "return redirect(url_for('kubernetes_operations.reveal_secret', reveal_view='mine'))" in block
    assert 'The KAORI app shell' not in block
    assert "'reveal_view': 'mine'" not in block
    assert (
        "return redirect(\n            url_for(\n                'kubernetes_operations.reveal_secret',\n                cluster_id=existing.cluster_id"
        in block
    )
    assert 'action_url=action_url' in block
    assert 'queue_feedback=True' in block


def test_short_step_up_guidance_and_canonical_pending_decision_actions() -> None:
    step_up = read('app/templates/kubernetes/operations/secrets/_reveal_step_up.html')
    pending = read('app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html')
    assert 'Session verified. Select Reveal Once on an approved request below.' in step_up
    assert 'Your session is verified. Choose Reveal Once' not in step_up
    assert 'table_ui.action_classes(destructive=true)' in pending
    assert 'value="deny"' in pending
    assert 'value="approve"' in pending
    assert 'class="{{ table_ui.action_classes() }}"' in pending
    assert 'name="csrf_token"' in pending
    assert "action_button.classes('primary')" not in pending


def test_secret_reveal_submit_restores_main_scroll_without_storing_sensitive_data() -> None:
    form = read('app/templates/kubernetes/operations/secrets/_reveal_request_form.html')
    script = read('app/static/js/secret_reveal_workspace.js')
    routes = read('app/kubernetes/operations/secrets/reveal_routes.py')
    inbox = read('app/kubernetes/operations/secrets/approval_inbox.py')
    decisions = read('app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html')

    assert 'data-reveal-request-submit-form' in form
    assert "window.sessionStorage.setItem(submittedNavigationKey, 'mine')" in script
    assert 'window.sessionStorage.removeItem(submittedNavigationKey)' in script
    assert "document.addEventListener('submit', markRequestNavigation)" in script
    assert "view !== 'mine'" in script
    assert "main?.scrollTo({ top: 0, behavior: 'auto' })" in script
    restore = script.split('const restoreSubmittedWorkspacePosition = () => {', 1)[1].split(
        'const schedulePolling = (root) => {', 1
    )[0]
    assert restore.count('window.requestAnimationFrame(() =>') == 2
    assert "if (view !== 'mine') return" in restore
    assert "main?.scrollTo({ top: 0, behavior: 'auto' })" in restore
    assert 'request.form' not in script
    assert "return redirect(url_for('kubernetes_operations.reveal_secret', reveal_view='mine'))" in routes
    assert '_notify_secret_reveal_approvers(result.request_record)' in routes
    assert 'get_secret_reveal_approvers(exclude_user_id=record.requester_user_id)' in routes
    assert "viewer.has_permission('kubernetes_secrets.approve_reveal')" in inbox
    assert 'SecretRevealRequest.requester_user_id != user_id' in inbox
    assert "SecretRevealRequest.status == 'pending'" in inbox
    assert 'value="deny"' in decisions
    assert 'value="approve"' in decisions
    assert 'table_ui.action_classes(destructive=true)' in decisions
    assert 'class="{{ table_ui.action_classes() }}"' in decisions
