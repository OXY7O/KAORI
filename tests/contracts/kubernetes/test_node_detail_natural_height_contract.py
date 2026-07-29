from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_node_detail_cards_follow_tallest_card_without_fixed_min_height() -> None:
    detail = _read("app/templates/inventory/nodes/partials/_node_detail_content.html")

    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert "flex h-full flex-col rounded-xl" in detail
    assert "flex self-start flex-col rounded-xl" not in detail

    # Equal height comes from the grid row, not an arbitrary fixed minimum.
    assert "min-h-80" not in detail
    assert "min-h-96" not in detail

    assert "inventory_tip.tip(message, icon, true)" in detail
    assert "detail_card('Node Identity', 'badge-info', node.role)" in detail
    assert "detail_card('Connectivity', 'network', node.scheduled_pod_count ~ ' Pods')" in detail
    assert "detail_card('Platform & Runtime', 'cpu', node.operating_system_display)" in detail
    assert "detail_card('Scheduling & Conditions', 'clipboard-check', condition_posture, 'status', condition_tone)" in detail
