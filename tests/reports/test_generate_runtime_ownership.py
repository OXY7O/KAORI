TEMPLATE_PATH = 'app/templates/reports/generate/index.html'
RUNTIME_PATH = 'app/static/js/reports/generate.js'


def _read(path: str) -> str:
    with open(path, encoding='utf-8') as file_handle:
        return file_handle.read()


def test_generate_report_runtime_has_static_owner() -> None:
    template = _read(TEMPLATE_PATH)
    runtime = _read(RUNTIME_PATH)

    assert runtime
    assert 'id="reports-generate-bootstrap"' in template
    assert 'type="application/json"' in template
    assert 'js/reports/generate.js' in template
    assert "document.addEventListener('DOMContentLoaded'" not in template


def test_generate_report_bootstrap_carries_server_rendered_runtime_state() -> None:
    template = _read(TEMPLATE_PATH)

    for payload_key in (
        'default_sections_by_report_type',
        'section_options_by_report_type',
        'report_type_options',
        'namespace_options_by_cluster',
    ):
        assert payload_key in template

    assert 'reports-generate-bootstrap' in template


def test_generate_report_runtime_supports_idempotent_initialization() -> None:
    runtime = _read(RUNTIME_PATH)

    assert 'data-reports-generate-initialized' in runtime
    assert 'htmx:afterSwap' in runtime
