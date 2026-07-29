from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "app/templates/inventory/storage/partials/_summary_cards.html"
TABLE = ROOT / "app/templates/inventory/storage/partials/_table_content.html"
DETAIL = ROOT / "app/templates/inventory/storage/partials/_storage_detail_content.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_storage_inventory_copy_uses_requested_display_capitalization() -> None:
    summary = read(SUMMARY)
    table = read(TABLE)

    expected = [
        "StorageClass, PV, and PVC Records",
        "Provisioning Classes Available",
        "Cluster Scoped Persistent Volumes",
        "Namespace Scoped Storage Claims",
        "Provisioning Classes in Scope",
        "Namespace Storage Claims in Scope",
    ]
    for copy in expected:
        assert copy in summary

    removed = [
        "StorageClass, PV, and PVC records.",
        "Provisioning classes available.",
        "Cluster-scoped persistent volumes.",
        "Namespace-scoped storage claims.",
        "Provisioning classes in scope.",
        "Namespace storage claims in scope.",
    ]
    for copy in removed:
        assert copy not in summary

    assert "{{ 'Storage Object' if pagination.total_items == 1 else 'Storage Objects' }}" in table
    assert "{{ 'storage object' if pagination.total_items == 1 else 'storage objects' }}" not in table


def test_storage_detail_cards_share_tallest_height_and_detail_label_scale() -> None:
    detail = read(DETAIL)

    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert "min-h-[30rem]" not in detail
    assert "min-h-[34rem]" not in detail

    assert detail.count("badge_size='detail'") >= 4
    assert "detail.status_row('Storage Class', storage_class_value, storage_class_tone, none, 'detail')" in detail
    assert "detail.status_row('Status', item.status, status_tone, none, 'detail')" in detail
    assert "detail.status_row('Reclaim Policy', reclaim_policy_value, reclaim_policy_tone, none, 'detail')" in detail


def test_storage_detail_requested_values_use_semantic_labels_and_boundary_tips_are_removed() -> None:
    detail = read(DETAIL)

    assert "normalized_storage_class == 'cstor-csi'" in detail
    assert "normalized_access_mode in ['readwriteonce', 'readwriteoncepod']" in detail
    assert "normalized_reclaim_policy == 'delete'" in detail
    assert "table_label.status_label(access_mode, access_mode_tone, none, 'detail')" in detail
    assert "detail.detail_card('Binding & Lifecycle', 'link-2', reclaim_policy_value, 'status', reclaim_policy_tone, badge_size='detail')" in detail

    for removed in [
        "Capacity Boundary",
        "Declared capacity only; filesystem utilization remains in Storage Analysis.",
        "Lifecycle Boundary",
        "Bindings and lifecycle controls reflect the current Kubernetes object state.",
    ]:
        assert removed not in detail
