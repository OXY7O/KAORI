from pathlib import Path


def test_configmap_create_queues_success_feedback_before_htmx_redirect():
    source = Path('app/kubernetes_operations/configmaps/routes.py').read_text()
    assert 'queue_feedback: bool | None = None' in source
    assert "queue_feedback=(request.headers.get('HX-Request') != 'true' or not dry_run)" in source
    assert "response.headers['HX-Redirect'] = redirect_url" in source


def test_configmap_validation_keeps_immediate_oob_feedback_behavior():
    source = Path('app/kubernetes_operations/configmaps/routes.py').read_text()
    assert "if dry_run and feedback.get('status') == 'success':" in source
    assert 'kaori:operation-validated' in source
