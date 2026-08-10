from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_protected_reveal_uses_integrated_workspace_tabs() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    tabs = read('app/templates/components/workspace_tabs.html')

    assert 'components/workspace_tabs.html' in page
    assert 'workspace_tabs.render(reveal_tabs' in page
    assert "reveal_view='new'" in page
    assert "reveal_view='mine'" in page
    assert 'data-kaori-tab-fallback="server-navigation"' in tabs
    assert 'components/segmented_tabs.html' not in page
    assert 'data-kaori-tab-variant="integrated-workspace"' in tabs
    assert "('new', 'New Request'" in page
    assert "('mine', 'My Requests'" in page
    assert "('approvals', 'Approvals'" in page
    assert 'my_reveal_pagination.total' in page
    assert 'pending_reveal_pagination.total' in page


def test_reveal_tab_state_uses_canonical_alpine_workspace_controller() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    routes = read('app/kubernetes_operations/secrets/reveal_routes.py')

    assert "'active_reveal_view': active_reveal_view" in routes
    assert "request.args.get('reveal_view')" in routes
    assert "activeTab: '{{ active_reveal_view }}'" in page
    assert 'setTab(tab)' in page
    assert "url.searchParams.set('reveal_view', tab)" in page
    assert 'window.history.replaceState' in page
    assert '#my-secret-reveal-requests' in page and "'mine'" in page
    assert '#pending-secret-reveal-approvals' in page and "'approvals'" in page


def test_reveal_tabs_switch_client_side_with_server_navigation_fallback() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    tabs = read('app/templates/components/workspace_tabs.html')

    assert '@click.prevent="setTab(' in tabs
    assert 'href="{{ tab_href }}"' in tabs
    assert 'data-kaori-tab-fallback="server-navigation"' in tabs
    assert "reveal_view='new'" in page
    assert "reveal_view='mine'" in page
    assert "x-show=\"activeTab === 'new'\"" in page
    assert "x-show=\"activeTab === 'mine'\"" in page
    assert "x-bind:hidden=\"activeTab !== 'new'\"" in page
    assert "x-bind:hidden=\"activeTab !== 'mine'\"" in page


def test_reveal_safety_contract_is_collapsed_by_default() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')

    assert "information_guide_card.render('Reveal Safety Contract'" in page
    assert "protected_reveal_guardrails, icon='shield-check', open_by_default=false" in page


def test_reveal_redirects_preserve_the_next_workspace_view() -> None:
    routes = read('app/kubernetes_operations/secrets/reveal_routes.py')

    assert "reveal_view='mine'" in routes
    assert "_anchor='my-secret-reveal-requests'" in routes
    assert "reveal_view='approvals'" in routes
    assert "_anchor='pending-secret-reveal-approvals'" in routes


def test_reveal_polling_only_runs_for_the_active_replaceable_panel() -> None:
    script = read('app/static/js/secret_reveal_workspace.js')
    request_status = read('app/templates/kubernetes_operations/secrets/_reveal_request_status.html')
    approvals = read('app/templates/kubernetes_operations/secrets/_reveal_pending_approvals.html')

    assert "const activePanel = (root) =>" in script
    assert '!panel.hidden' in script
    assert "querySelector('[data-reveal-poll-owner]')" in script
    assert 'window.setInterval' in script
    assert "secret-reveal:tab-changed" in script
    assert 'data-reveal-poll-owner' in request_status
    assert 'data-reveal-poll-owner' in approvals
    assert 'hx-trigger="every 4s"' not in request_status
    assert 'hx-trigger="every 4s"' not in approvals


def test_reveal_pagination_is_scoped_to_its_partial_owner() -> None:
    request_status = read('app/templates/kubernetes_operations/secrets/_reveal_request_status.html')
    approvals = read('app/templates/kubernetes_operations/secrets/_reveal_pending_approvals.html')

    assert "'kubernetes_operations.reveal_secret_status'" in request_status
    assert "'#secret-reveal-request-status'" in request_status
    assert "'kubernetes_operations.reveal_secret_approvals'" in approvals
    assert "'#pending-secret-reveal-approvals'" in approvals


def test_one_time_value_uses_protected_value_panel_and_clearing_script() -> None:
    partial = read('app/templates/kubernetes_operations/secrets/_reveal_value.html')
    panel = read('app/templates/components/protected_value_panel.html')
    script = read('app/static/js/secret_reveal_value.js')

    assert 'components/protected_value_panel.html' in partial
    assert 'data-protected-value-panel' in panel
    assert 'data-protected-value-countdown' in panel
    assert 'visibilitychange' in script
    assert 'pagehide' in script
    assert 'htmx:beforeSwap' in script
    assert 'clipboard' not in panel.lower()
