from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pod_inventory_summary_copy_is_title_case_without_periods() -> None:
    source = read("app/templates/inventory/pods/partials/_summary_cards.html")
    expected = [
        "Pods In The Current Result",
        "Pods Currently In Running Phase",
        "Distinct Container Images Observed",
        "Container Image References Across Pods",
        "Pods Waiting For Scheduling Or Startup",
        "Pods Requiring Runtime Investigation",
    ]
    for text in expected:
        assert text in source
        assert f"{text}." not in source


def test_pod_inventory_footer_uses_title_case_count_label() -> None:
    source = read("app/templates/inventory/pods/partials/_table_content.html")
    assert "</span> of <span" in source
    assert "'Pod' if pagination.total_items == 1 else 'Pods'" in source
    assert "</span> Of <span" not in source


def test_pod_detail_removes_requested_guidance_boxes() -> None:
    source = read("app/templates/inventory/pods/partials/_pod_detail_content.html")
    assert "info_box('Network Identity'" not in source
    assert "Pod IP identifies the Pod; Host IP identifies its node." not in source
    assert "info_box('Snapshot Boundary'" not in source
    assert "Conditions are snapshot data; history remains in Analytics." not in source
    assert "Placement & Network" in source
    assert "Pod Configuration" in source
