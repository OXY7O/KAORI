from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KPI_CARDS = ROOT / "app/templates/inventory/overview/partials/_kpi_cards.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_inventory_overview_header_metrics_are_centered_and_right_aligned() -> None:
    template = read(KPI_CARDS)

    assert "lg:flex-row lg:items-center lg:justify-between" in template
    assert "flex w-full flex-wrap items-center justify-end gap-2 sm:w-auto lg:ml-auto" in template
    assert template.count("items-center justify-center gap-2 rounded-md") >= 2
    assert template.count("text-center text-xs font-semibold") >= 2


def test_inventory_overview_supporting_copy_matches_requested_case_and_punctuation() -> None:
    template = read(KPI_CARDS)

    expected = [
        "Objects per Cluster",
        "Maximum Collection Age",
        "Connected Inventory Targets",
        "Within the Freshness Window",
    ]
    for copy in expected:
        assert copy in template

    removed = [
        "Objects per cluster.",
        "Maximum collection age.",
        "Connected inventory targets.",
        "Within the freshness window.",
    ]
    for copy in removed:
        assert copy not in template
