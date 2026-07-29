from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_workload_inventory_summary_copy_is_title_case_without_periods() -> None:
    template = _read("app/templates/inventory/workloads/partials/_summary_cards.html")

    expected = (
        "Deployments, StatefulSets, And DaemonSets",
        "% Of Matching Workloads",
        "State-Aware Workloads With Stable Identity",
        "Node-Level Agents And Platform Components",
        "Rollouts Currently Progressing",
        "Workloads Outside Running Or Progressing",
    )
    for copy in expected:
        assert copy in template

    forbidden = (
        "Deployments, StatefulSets, and DaemonSets.",
        "% of matching workloads.",
        "State-aware workloads with stable identity.",
        "Node-level agents and platform components.",
        "Rollouts currently progressing.",
        "Workloads outside Running or Progressing.",
    )
    for copy in forbidden:
        assert copy not in template


def test_workload_inventory_footer_uses_title_case() -> None:
    template = _read("app/templates/inventory/workloads/partials/_table_content.html")
    assert "</span> Of <span" in template
    assert "'Workload' if pagination.total_items == 1 else 'Workloads'" in template


def test_delivery_placement_tip_is_removed() -> None:
    template = _read("app/templates/inventory/workloads/partials/_workload_detail_content.html")
    assert "Placement rules guide scheduling; actual placement is shown in Pod inventory." not in template
    assert "detail.detail_card('Delivery & Placement'" in template
