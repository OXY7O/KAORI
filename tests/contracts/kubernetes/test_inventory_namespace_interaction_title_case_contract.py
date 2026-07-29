from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_inventory_pagination_copy_uses_title_case():
    cluster = read("app/templates/inventory/overview/partials/_resources_by_cluster_content.html")
    namespace = read("app/templates/inventory/namespaces/partials/_table_content.html")
    assert "of <span" in cluster
    assert "'Cluster' if" in cluster and "'Clusters'" in cluster
    assert "of <span" in namespace
    assert "'Namespace' if" in namespace and "'Namespaces'" in namespace


def test_namespace_summary_copy_is_title_case_without_periods():
    template = read("app/templates/inventory/namespaces/partials/_summary_cards.html")
    expected = [
        "Namespaces In The Current Scope",
        "Clusters Contributing Namespace Inventory",
        "Namespaces In Active Lifecycle State",
        "Namespaces Outside Active State",
        "Available For Workload Placement",
        "Namespaces Requiring Lifecycle Review",
    ]
    for copy in expected:
        assert copy in template
        assert f"{copy}." not in template


def test_expandable_rows_use_deterministic_fetch_request_flow():
    macro = read("app/templates/components/details/_expandable_row.html")
    script = read("app/static/js/detail_rows.js")
    assert 'data-detail-url="{{ detail_url or' in macro
    assert "event.stopImmediatePropagation()" not in script
    assert "fetch(detailUrl" in script
    assert "credentials: 'same-origin'" in script
    assert "'HX-Request': 'true'" in script
    assert "renderLoading(target)" in script
    assert "target.dataset.open = 'true'" in script
    assert "window.htmx?.process" in script
    assert 'hx-get="{{ detail_url }}"' not in macro
