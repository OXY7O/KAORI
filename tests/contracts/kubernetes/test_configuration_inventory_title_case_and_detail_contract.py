from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "app/templates/inventory/configuration/partials/_summary_cards.html"
TABLE = ROOT / "app/templates/inventory/configuration/partials/_table_content.html"
DETAIL = ROOT / "app/templates/inventory/configuration/partials/_configuration_detail_content.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_configuration_inventory_copy_uses_requested_display_capitalization() -> None:
    summary = read(SUMMARY)
    table = read(TABLE)

    expected = [
        "ConfigMap and Secret Records",
        "Non-sensitive Configuration Metadata",
        "Secret Metadata and Key Names Only",
        "Objects Configured as Immutable",
        "Values Remain Protected, Metadata Only",
        "Objects Protected from Mutation",
    ]
    for copy in expected:
        assert copy in summary

    removed = [
        "ConfigMap and Secret records.",
        "Non-sensitive configuration metadata.",
        "Secret metadata and key names only.",
        "Objects configured as immutable.",
        "Values remain protected; metadata only.",
        "Objects protected from mutation.",
    ]
    for copy in removed:
        assert copy not in summary

    assert "{{ 'Object' if pagination.total_items == 1 else 'Objects' }}" in table
    assert "{{ 'object' if pagination.total_items == 1 else 'objects' }}" not in table


def test_configuration_detail_uses_four_equal_height_cards_and_detail_scale() -> None:
    detail = read(DETAIL)

    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert detail.count("detail.detail_card(") == 4
    assert detail.count("badge_size='detail'") == 4
    assert "min-h-[26rem]" not in detail

    for card_title in [
        "Object Identity",
        "Key Metadata",
        "Protection State",
        "Used By Pods",
    ]:
        assert card_title in detail

    assert "table_label.metadata_label(key_name, none, true, 'detail')" in detail
    assert "table_label.status_label(pod.status, pod_tone, none, 'detail')" in detail


def test_configuration_type_uses_semantic_label_and_boundary_tips_are_removed() -> None:
    table = read(TABLE)
    detail = read(DETAIL)

    assert "normalized_object_type == 'configmap'" in detail
    assert "object_type_tone = 'normal'" in detail
    assert "detail.status_row('Type', object_type_value, object_type_tone, none, 'detail')" in detail
    assert "table_label.status_label(object_type_value, object_type_tone, none, 'detail')" in detail
    assert "table_label.status_label(item.type, item_type_tone)" in table

    for removed in [
        "Metadata Boundary",
        "Key names are visible; configuration and Secret values are excluded.",
        "Reference Boundary",
        "Consumers reflect environment and mounted configuration references in the current snapshot.",
    ]:
        assert removed not in detail
