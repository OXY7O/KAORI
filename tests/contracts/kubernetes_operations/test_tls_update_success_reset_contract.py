from pathlib import Path

ROUTES = Path('app/kubernetes_operations/secrets/tls_routes.py')


def test_successful_single_tls_update_redirects_to_fresh_rotation_workspace():
    source = ROUTES.read_text()
    assert 'def _tls_workspace_redirect(location: str):' in source
    assert "response.headers['HX-Redirect'] = location" in source
    assert "url_for('kubernetes_operations.tls_secret_rotate', certificate_id=certificate_id)" in source


def test_successful_bulk_tls_update_queues_toast_and_resets_workspace():
    source = ROUTES.read_text()
    assert 'queue_feedback=is_success' in source
    assert "url_for('kubernetes_operations.tls_secret_bulk_rotation')" in source
    assert 'if is_success:\n        return _tls_workspace_redirect(' in source


def test_partial_or_failed_bulk_update_keeps_diagnostic_result_in_place():
    source = ROUTES.read_text()
    success_redirect = source.index('if is_success:\n        return _tls_workspace_redirect(')
    feedback_render = source.index("'kubernetes_operations/secrets/_bulk_feedback.html'", success_redirect)
    assert feedback_render > success_redirect
