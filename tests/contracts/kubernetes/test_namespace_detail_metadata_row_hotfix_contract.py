from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_detail_component_exposes_metadata_row() -> None:
    component = read("app/templates/components/details/_detail_content.html")

    assert "macro metadata_row(label, value='-', icon=None, wrap=False)" in component
    assert "table_label.metadata_label(display_value, icon, wrap, 'detail')" in component


def test_namespace_psa_rows_use_supported_shared_macro() -> None:
    namespace_detail = read(
        "app/templates/inventory/namespaces/partials/_namespace_detail_content.html"
    )

    assert namespace_detail.count("detail.metadata_row(") == 3
    assert "detail.metadata_row('Enforce', psa_enforce_display)" in namespace_detail
    assert "detail.metadata_row('Audit', psa_audit_display)" in namespace_detail
    assert "detail.metadata_row('Warn', psa_warn_display)" in namespace_detail


def test_metadata_row_macro_can_be_imported_and_rendered() -> None:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = environment.from_string(
        "{% import 'components/details/_detail_content.html' as detail %}"
        "{{ detail.metadata_row('Enforce', 'Restricted') }}"
    )

    rendered = template.render()

    assert "Enforce" in rendered
    assert "Restricted" in rendered
    assert "kaori-semantic-label" in rendered
