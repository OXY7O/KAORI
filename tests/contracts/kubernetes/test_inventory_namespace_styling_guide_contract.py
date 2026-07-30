from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_namespace_inventory_applies_resource_page_pattern() -> None:
    hero = read("app/templates/inventory/namespaces/partials/_hero.html")
    summary = read("app/templates/inventory/namespaces/partials/_summary_cards.html")
    table = read("app/templates/inventory/namespaces/partials/_table_content.html")

    assert "page_hero.context_card(" in hero
    assert "Namespace Control Posture" in summary
    assert "posture_grid.render(posture_metrics, columns=3)" in summary
    for column in (
        "Namespace",
        "Cluster",
        "Lifecycle",
        "Resource Controls",
        "Security Context",
        "Details",
    ):
        assert f">{column}</th>" in table or column in table
    assert "status_indicator_label(namespace.lifecycle_label" in table
    assert 'resource_detail_modal.detail_button(' in table


def test_namespace_lifecycle_and_policy_semantics_are_factual() -> None:
    service = read("app/inventory/resources/namespaces.py")
    detail = read("app/templates/inventory/namespaces/partials/_namespace_detail_content.html")

    assert "'Transitioning', 'info'" in service
    assert "'Review Required', 'warning'" in service
    assert "does not automatically indicate a compliance failure" in detail
    assert "Inherited or absent namespace-level controls remain neutral evidence" in detail
    assert "Available For Workload Placement" not in detail


def test_namespace_detail_uses_shared_metadata_and_operational_context() -> None:
    detail = read("app/templates/inventory/namespaces/partials/_namespace_detail_content.html")
    component = read("app/templates/components/technical_metadata_collection.html")

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert "technical_metadata_collection.html" in detail
    assert detail.count("metadata_collection.render(") == 2
    assert "Operational Context" in detail
    assert "Committed Snapshot Boundary" in detail
    assert "macro render(title, entries" in component
    assert "max-h-56 overflow-y-auto" not in component
    assert "overflow-hidden rounded-lg border" in component


def test_namespace_pagination_stays_htmx_aware() -> None:
    table = read("app/templates/inventory/namespaces/partials/_table_content.html")
    assert '>Rows</label>' in table
    assert "endpoint='inventory.namespaces'" in table
    assert "hx_target='#namespaces-table-content'" in table
    assert "hx_indicator='#namespaces-table-loading'" in table
