from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "app/templates/reports/generate/index.html"
RUNTIME_PATH = ROOT / "app/static/js/reports/generate.js"


def test_generate_report_runtime_has_static_owner() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert RUNTIME_PATH.is_file()
    assert 'id="reports-generate-bootstrap"' in template
    assert 'type="application/json"' in template
    assert "js/reports/generate.js" in template
    assert "document.addEventListener('DOMContentLoaded'" not in template


def test_generate_report_bootstrap_carries_server_rendered_runtime_state() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    for payload_key in (
        "default_sections_by_report_type",
        "section_options_by_report_type",
        "report_type_options",
        "namespace_options_by_cluster",
    ):
        assert payload_key in template

    assert "reports-generate-bootstrap" in template


def test_generate_report_runtime_supports_idempotent_initialization() -> None:
    runtime = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "data-reports-generate-initialized" in runtime
    assert "htmx:afterSwap" in runtime
