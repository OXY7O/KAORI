from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_shared_detail_component_supports_explicit_label_scale() -> None:
    component = _read('app/templates/components/details/_detail_content.html')
    assert "macro status_row(label, value, tone='unknown', icon=None, size='compact')" in component
    assert 'table_label.status_label(value, tone, icon, size)' in component
    assert "badge_size='compact'" in component


def test_namespace_primary_detail_cards_use_detail_sized_labels() -> None:
    detail = _read('app/templates/inventory/namespaces/partials/_namespace_detail_content.html')
    assert detail.count("badge_size='detail'") == 4
    assert "detail.detail_card('Namespace Identity', 'badge-info', namespace.age" in detail
    assert "stretch=false, density='compact'" in detail
    assert "detail.detail_card('Object Composition', 'boxes'" in detail
    assert "detail.detail_card('Access & Security', 'shield-check'" in detail
    assert 'status_indicator_label(namespace.lifecycle_label' in detail
    assert "('Default ServiceAccount', namespace.default_service_account" in detail
