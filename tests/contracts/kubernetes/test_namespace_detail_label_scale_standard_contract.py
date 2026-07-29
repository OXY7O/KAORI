from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_detail_component_supports_explicit_label_scale() -> None:
    component = _read("app/templates/components/details/_detail_content.html")

    assert "macro status_row(label, value, tone='unknown', icon=None, size='compact')" in component
    assert "table_label.status_label(value, tone, icon, size)" in component
    assert "badge_size='compact'" in component
    assert "table_label.status_label(badge, badge_tone, none, badge_size)" in component
    assert "table_label.metadata_label(badge, none, false, badge_size)" in component


def test_namespace_primary_detail_cards_use_detail_sized_labels() -> None:
    detail = _read(
        "app/templates/inventory/namespaces/partials/_namespace_detail_content.html"
    )

    assert detail.count("badge_size='detail'") == 4
    assert "detail.detail_card('Namespace Identity', 'badge-info', namespace.age, badge_size='detail')" in detail
    assert "detail.detail_card('Resource Inventory', 'boxes'" in detail
    assert "detail.detail_card('Resource Controls', 'sliders-horizontal'" in detail
    assert "detail.detail_card('Security & Access', 'shield-check'" in detail

    # Semantic status labels inside the four cards use the same detail scale
    # as the surrounding card content instead of the compact table scale.
    assert detail.count("size='detail'") >= 6
    assert "detail.status_row('Status', namespace.status, namespace_status_tone, size='detail')" in detail
    assert "detail.status_row('Default ServiceAccount', namespace.default_service_account, default_sa_tone, size='detail')" in detail
