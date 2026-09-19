from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_configmap_create_queues_success_feedback_before_htmx_redirect() -> None:
    source = read('app/kubernetes/operations/configmaps/routes.py')

    assert 'queue_feedback = not _is_htmx() or not validate_only' in source
    assert "if not validate_only and feedback.get('status') == 'success':" in source
    assert "response.headers['HX-Redirect'] = redirect_url" in source
    assert "'feedback_delivery': 'toast'" in source


def test_configmap_validation_returns_canonical_oob_feedback_and_preview() -> None:
    routes = read('app/kubernetes/operations/configmaps/routes.py')
    response = read('app/templates/kubernetes/operations/configmaps/_operation_response.html')

    assert 'kaori:operation-validated' in routes
    assert 'components/operation_feedback_oob.html' in response
    assert '_validation_preview.html' in response
    assert "form_id == 'configmap-delete-form'" in response
