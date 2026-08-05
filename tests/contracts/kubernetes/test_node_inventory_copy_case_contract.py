from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "app/templates/inventory/nodes/partials/_summary_cards.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_node_inventory_supporting_copy_uses_kaori_sentence_case() -> None:
    template = read(SUMMARY)

    expected = [
        "inventory.cpu_coverage_description",
        "inventory.memory_coverage_description",
        "inventory.ephemeral_coverage_description",
        "Nodes excluded from new workload scheduling.",
        "Nodes reporting memory, disk, or PID pressure.",
        "Nodes reporting an unavailable network condition.",
    ]
    for copy in expected:
        assert copy in template

    removed = [
        "Reported CPU Capacity In The Active Node Scope.",
        "Reported Memory Capacity Across Filtered Nodes.",
        "Nodes Excluded From New Workload Scheduling.",
    ]
    for copy in removed:
        assert copy not in template


def test_node_inventory_copy_keeps_technical_acronyms() -> None:
    template = read(SUMMARY)

    assert "Total CPU" in template
    assert "total_memory_display" in template
    assert "total_ephemeral_storage_display" in template
    assert "PID pressure" in template
