from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "app/templates/inventory/nodes/partials/_summary_cards.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_node_inventory_supporting_copy_uses_kaori_display_case() -> None:
    template = read(SUMMARY)

    expected = [
        "Nodes in the Current Scope",
        "Reported Memory Capacity in GiB",
        "Local Ephemeral Capacity in GiB",
        "Available for Workload Scheduling",
        "% of Nodes Require Attention",
    ]
    for copy in expected:
        assert copy in template

    removed = [
        "Nodes In The Current Scope",
        "Reported Memory Capacity In GiB",
        "Local Ephemeral Capacity In GiB",
        "Available For Workload Scheduling",
        "% Of Nodes Require Attention",
    ]
    for copy in removed:
        assert copy not in template


def test_node_inventory_copy_keeps_technical_acronyms() -> None:
    template = read(SUMMARY)

    assert "Reported CPU Cores" in template
    assert "GiB" in template
