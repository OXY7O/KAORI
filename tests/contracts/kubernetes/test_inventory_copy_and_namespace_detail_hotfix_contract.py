from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_inventory_overview_and_pagination_copy() -> None:
    kpis = read("app/templates/inventory/overview/partials/_kpi_cards.html")
    clusters = read("app/templates/inventory/overview/partials/_resources_by_cluster_content.html")
    namespaces = read("app/templates/inventory/namespaces/partials/_table_content.html")

    assert "Objects per Cluster." in kpis
    assert "Within the Freshness Window." in kpis
    assert "\n            of <span" in clusters
    assert "\n            of <span" in namespaces
    assert "\n            Of <span" not in clusters
    assert "\n            Of <span" not in namespaces


def test_node_summary_copy_has_no_trailing_periods_and_tip_is_removed() -> None:
    summary = read("app/templates/inventory/nodes/partials/_summary_cards.html")
    detail = read("app/templates/inventory/nodes/partials/_node_detail_content.html")

    expected = (
        "Nodes In The Current Scope",
        "Reported CPU Cores",
        "Reported Memory Capacity In GiB",
        "Local Ephemeral Capacity In GiB",
        "Available For Workload Scheduling",
        "% Of Nodes Require Attention",
    )
    for text in expected:
        assert text in summary
        assert f"{text}." not in summary

    assert "Conditions show current readiness, pressure, and scheduling state." not in detail


def test_namespace_detail_card_calls_match_shared_macro_signature() -> None:
    detail = read("app/templates/inventory/namespaces/partials/_namespace_detail_content.html")
    macro = read("app/templates/components/details/_detail_content.html")

    assert "macro detail_card(title, icon, badge=None, badge_type='metadata', badge_tone='unknown', class_name='', badge_size='compact')" in macro
    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert ", None, 'min-h-96'" not in detail
    assert ", None, 'min-h-[28rem]'" not in detail
    assert "min-h-96" not in detail
    assert "min-h-[28rem]" not in detail
    assert "detail.detail_card('Namespace Identity', 'badge-info', namespace.age, badge_size='detail')" in detail
    assert detail.count("detail.detail_card(") == 4
