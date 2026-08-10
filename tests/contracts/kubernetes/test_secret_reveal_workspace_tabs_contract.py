from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_protected_reveal_uses_integrated_workspace_tabs() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    tabs = read('app/templates/components/workspace_tabs.html')

    assert 'components/workspace_tabs.html' in page
    assert 'workspace_tabs.render_controlled' in page
    assert 'components/segmented_tabs.html' not in page
    assert 'macro render_controlled' in tabs
    assert 'data-kaori-tab-variant="integrated-workspace"' in tabs
    assert "('new', 'New Request'" in page
    assert "('mine', 'My Requests'" in page
    assert "('approvals', 'Approvals'" in page
    assert 'my_reveal_pagination.total' in page
    assert 'pending_reveal_pagination.total' in page


def test_reveal_tab_state_is_url_and_deep_link_aware() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')
    routes = read('app/kubernetes_operations/secrets/reveal_routes.py')
    script = read('app/static/js/secret_reveal_workspace.js')

    assert "'active_reveal_view': active_reveal_view" in routes
    assert "request.args.get('reveal_view')" in routes
    assert 'data-secret-reveal-active-view="{{ active_reveal_view }}"' in page
    assert "const viewParam = 'reveal_view';" in script
    assert "['#my-secret-reveal-requests', 'mine']" in script
    assert "['#pending-secret-reveal-approvals', 'approvals']" in script
    assert 'resolveTabFromLocation' in script
    assert 'window.history.replaceState' in script



def test_reveal_refresh_keeps_server_rendered_panel_until_view_pair_is_validated() -> None:
    script = read('app/static/js/secret_reveal_workspace.js')

    assert 'const viewState = (root) =>' in script
    assert 'const activeTab = state.tabByKey.get(key);' in script
    assert 'const activePanel = state.panelByKey.get(key);' in script
    assert 'return false;' in script
    assert "root.dataset.secretRevealActiveView = key;" in script
    assert "panel.toggleAttribute('hidden', panel !== activePanel);" in script
    assert 'const serverVisiblePanel = state.panels.find((panel) => !panel.hidden);' in script

    query_position = script.index('new URL(window.location.href).searchParams.get(viewParam)')
    hash_position = script.index('const hashView = deepLinkViews.get(window.location.hash);')
    server_position = script.index('const serverView = root.dataset.secretRevealActiveView;')
    assert query_position < hash_position < server_position

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

    assert 'panel.hidden' in script
    assert "querySelector('[data-reveal-poll-owner]')" in script
    assert 'window.setInterval' in script
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
