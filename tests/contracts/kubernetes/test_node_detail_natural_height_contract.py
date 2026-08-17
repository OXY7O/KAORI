from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_node_detail_cards_follow_tallest_card_without_fixed_min_height() -> None:
    detail = _read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = _read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'grid items-stretch gap-4 p-5 md:grid-cols-2 2xl:grid-cols-3' in detail
    assert 'stretch=true' in shared
    assert "{{ 'h-full' if stretch else '' }}" in shared

    # Equal height comes from the grid row, not an arbitrary fixed minimum.
    assert 'min-h-80' not in detail
    assert 'min-h-96' not in detail

    assert "detail.detail_card('Node Identity'" in detail
    assert "detail.detail_card('Node Capacity'" in detail
    assert "detail.detail_card('Connectivity'" in detail
    assert "detail.detail_card('Platform & Runtime'" in detail
    assert "detail.detail_card('Scheduling & Conditions'" in detail
    assert 'Committed Snapshot Boundary' in detail
