from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_protected_reveal_uses_segmented_workspaces() -> None:
    source = read('app/templates/kubernetes_operations/secrets/reveal.html')

    assert 'components/segmented_tabs.html' in source
    assert "('new', 'New Request'" in source
    assert "('mine', 'My Requests'" in source
    assert "('approvals', 'Approvals'" in source
    assert 'data-secret-reveal-panel="new"' in source
    assert 'data-secret-reveal-panel="mine"' in source
    assert 'data-secret-reveal-panel="approvals"' in source
    assert 'hx-trigger="every 4s"' not in source


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
