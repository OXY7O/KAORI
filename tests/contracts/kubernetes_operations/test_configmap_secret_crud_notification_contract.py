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

    support = read('app/kubernetes_operations/secrets/route_support.py')
    assert 'record_operational_activity' in support


def test_secret_crud_operation_responses_are_toast_only() -> None:
    expected_sinks = {
        '_create_operation_result.html': 'secret-operation-feedback',
        '_replace_operation_result.html': 'replace-secret-operation-feedback',
        '_delete_operation_result.html': 'secret-delete-operation-feedback',
    }
    templates = ROOT / 'app' / 'templates' / 'kubernetes_operations' / 'secrets'

    for filename, sink_id in expected_sinks.items():
        source = (templates / filename).read_text()
        assert 'components/operation_feedback_oob.html' in source
        assert 'operation_result_panel.html' not in source
        assert 'operation_result.render' not in source
        assert f'id="{sink_id}"' in source
        assert 'class="hidden"' in source
        assert 'aria-hidden="true"' in source
