from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_configmap_mutations_queue_feedback_before_redirect() -> None:
    source = read('app/kubernetes_operations/configmaps/routes.py')

    assert 'queue_feedback = not _is_htmx() or not validate_only' in source
    assert 'queue_feedback=not _is_htmx() or not validate_only' in source
    assert "response.headers['HX-Redirect'] = redirect_url" in source
    assert "'feedback_delivery': 'toast'" in source


def test_secret_mutations_use_canonical_operational_feedback_component() -> None:
    templates = ROOT / 'app' / 'templates' / 'kubernetes_operations' / 'secrets'
    for template in templates.glob('*_result.html'):
        source = template.read_text()
        assert 'components/navigation/_operation_feedback_oob.html' not in source

    routes = read('app/kubernetes_operations/secrets/routes.py')
    assert 'record_operational_activity' in routes
