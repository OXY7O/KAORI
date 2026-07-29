from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "app/templates/inventory/ingresses/partials/_summary_cards.html"
TABLE = ROOT / "app/templates/inventory/ingresses/partials/_table_content.html"
DETAIL = ROOT / "app/templates/inventory/ingresses/partials/_ingress_detail_content.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ingress_inventory_copy_uses_requested_display_capitalization() -> None:
    summary = read(SUMMARY)
    table = read(TABLE)

    expected = [
        "Ingress Resources in the Current Result",
        "Ingresses with TLS Configuration",
        "Unique Declared Hostnames",
        "Namespaces Publishing Ingress Routes",
        "Unique Hostnames in the Current Scope",
        "Ingresses Requiring Encryption Review",
    ]
    for copy in expected:
        assert copy in summary

    removed = [
        "Ingress resources in the current result.",
        "Ingresses with TLS configuration.",
        "Unique declared hostnames.",
        "Namespaces publishing ingress routes.",
        "Unique hostnames in the current scope.",
        "Ingresses requiring encryption review.",
    ]
    for copy in removed:
        assert copy not in summary

    assert "{{ 'Ingress' if pagination.total_items == 1 else 'Ingresses' }}" in table
    assert "{{ 'ingress' if pagination.total_items == 1 else 'ingresses' }}" not in table


def test_ingress_detail_cards_share_tallest_height_and_detail_label_scale() -> None:
    detail = read(DETAIL)

    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert "min-h-[30rem]" not in detail
    assert "min-h-[32rem]" not in detail
    assert "min-h-[34rem]" not in detail

    assert detail.count("badge_size='detail'") >= 4
    assert "table_label.status_label(ingress_class_value, ingress_class_tone, none, 'detail')" in detail
    assert "detail.status_row('Ingress Class', ingress_class_value, ingress_class_tone, none, 'detail')" in detail
    assert "normalized_ingress_class == 'nginx'" in detail


def test_ingress_detail_boundary_tips_and_requested_label_icons_are_removed() -> None:
    detail = read(DETAIL)

    for removed in [
        "Exposure Boundary",
        "TLS Boundary",
        "Routing Boundary",
        "Addresses appear after the controller publishes status.",
        "Secret references only; validity remains in TLS Governance.",
        "Routes show configuration, not traffic or latency.",
    ]:
        assert removed not in detail

    assert "metadata_label(table_label.count_text(ingress.backend_count, 'Route'), none, false, 'detail')" in detail
    assert "metadata_label(table_label.count_text(ingress.annotations|length, 'Annotation'), none, false, 'detail')" in detail
    assert "label_icon = none if key == 'app.kubernetes.io/instance' else 'tag'" in detail

    assert "metadata_label(table_label.count_text(ingress.backend_count, 'Route'), 'route')" not in detail
    assert "metadata_label(table_label.count_text(ingress.annotations|length, 'Annotation'), 'braces')" not in detail
