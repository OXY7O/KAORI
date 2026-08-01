from pathlib import Path


def test_configmap_mutations_queue_feedback_before_redirect():
    source = Path('app/kubernetes_operations/configmaps/routes.py').read_text()
    assert 'queue_feedback: bool | None = None' in source
    assert "or not dry_run" in source
    assert "or not validate_only" in source
    assert source.count("response.headers['HX-Redirect']") >= 3


def test_secret_mutations_queue_feedback_before_redirect():
    source = Path('app/kubernetes_operations/secrets/routes.py').read_text()
    assert 'queue_feedback=(not is_htmx or not dry_run)' in source
    assert 'queue_feedback=(not is_htmx or not validate_only)' in source
    assert source.count("response.headers['HX-Redirect']") >= 3
