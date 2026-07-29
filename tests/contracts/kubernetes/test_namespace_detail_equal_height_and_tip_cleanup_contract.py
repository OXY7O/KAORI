from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_namespace_detail_cards_follow_the_tallest_card() -> None:
    detail = _read(
        "app/templates/inventory/namespaces/partials/_namespace_detail_content.html"
    )
    shared_detail = _read("app/templates/components/details/_detail_content.html")

    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert 'class="flex h-full flex-col rounded-xl' in shared_detail

    # Height is determined by the tallest grid item, not fixed minimum classes.
    assert "min-h-96" not in detail
    assert "min-h-[28rem]" not in detail

    assert "detail.detail_card('Namespace Identity', 'badge-info', namespace.age, badge_size='detail')" in detail
    assert "detail.detail_card('Resource Inventory', 'boxes'" in detail
    assert "detail.detail_card('Resource Controls', 'sliders-horizontal'" in detail
    assert "detail.detail_card('Security & Access', 'shield-check'" in detail


def test_namespace_detail_removes_tip_boxes_from_cards_two_to_four() -> None:
    detail = _read(
        "app/templates/inventory/namespaces/partials/_namespace_detail_content.html"
    )

    assert "Only non-zero workload kinds are shown" not in detail
    assert "Quota and limit data show configured constraints" not in detail
    assert "PSA labels define namespace-level enforce, audit, and warn behavior" not in detail

    # The identity card guidance remains available.
    assert "Age comes from creation time; Collected is the latest KAORI snapshot." in detail
