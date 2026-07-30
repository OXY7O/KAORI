from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_inventory_overview_and_pagination_copy() -> None:
    catalog = read("app/templates/inventory/overview/partials/_kpi_cards.html")
    clusters = read("app/templates/inventory/overview/partials/_resources_by_cluster_content.html")
    namespaces = read("app/templates/inventory/namespaces/partials/_table_content.html")

    assert "Inventory Asset Catalog" in catalog
    assert "Open one Kubernetes asset inventory" in catalog
    assert "{{ 'Cluster' if overview.resources_pagination.total_items == 1 else 'Clusters' }}" in clusters
    assert ">Rows</label>" in clusters
    assert "\n                of <span" in clusters
    assert "\n            of <span" in namespaces
    assert "\n                Of <span" not in clusters
    assert "\n            Of <span" not in namespaces


def test_node_posture_copy_is_functional_and_does_not_duplicate_hero_readiness() -> None:
    summary = read("app/templates/inventory/nodes/partials/_summary_cards.html")
    detail = read("app/templates/inventory/nodes/partials/_node_detail_content.html")

    expected = (
        "Node Resource Posture",
        "Reported CPU capacity in the active node scope.",
        "Reported memory capacity across filtered nodes.",
        "Reported local ephemeral storage capacity.",
        "Nodes excluded from new workload scheduling.",
        "Nodes reporting memory, disk, or PID pressure.",
        "Nodes reporting unavailable network condition.",
    )
    for text in expected:
        assert text in summary

    assert "Ready Ratio" not in summary
    assert "Ready Nodes" not in summary
    assert "Not Ready Nodes" not in summary
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
