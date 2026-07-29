from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_inventory_overview_supporting_copy_uses_title_case() -> None:
    content = _read("app/templates/inventory/overview/partials/_kpi_cards.html")

    expected = (
        "Committed Inventory Coverage.",
        "Objects Per Cluster.",
        "Maximum Collection Age.",
        "Connected Inventory Targets.",
        "Within The Freshness Window.",
    )
    for label in expected:
        assert label in content

    rejected = (
        "Committed inventory coverage.",
        "Objects per cluster.",
        "Maximum collection age.",
        "Connected inventory targets.",
        "Within the freshness window.",
    )
    for label in rejected:
        assert label not in content


def test_node_inventory_supporting_copy_and_footer_use_title_case() -> None:
    summary = _read("app/templates/inventory/nodes/partials/_summary_cards.html")
    table = _read("app/templates/inventory/nodes/partials/_table_content.html")

    expected = (
        "Nodes In The Current Scope.",
        "Reported CPU Cores.",
        "Reported Memory Capacity In GiB.",
        "Local Ephemeral Capacity In GiB.",
        "Available For Workload Scheduling.",
        "% Of Nodes Require Attention.",
    )
    for label in expected:
        assert label in summary

    assert "{{ 'Node' if pagination.total_items == 1 else 'Nodes' }}" in table
    assert "{{ 'node' if pagination.total_items == 1 else 'nodes' }}" not in table
