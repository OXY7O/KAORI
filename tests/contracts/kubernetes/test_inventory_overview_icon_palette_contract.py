from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_asset_identity_icons_use_the_kaori_violet_palette() -> None:
    asset_card = read('app/templates/components/inventory_asset_card.html')

    assert 'data-kaori-inventory-identity-icon' in asset_card
    assert 'border-kaori-primary/15 bg-kaori-soft text-kaori-primary' in asset_card

    forbidden_identity_palette_tokens = (
        'bg-cyan-',
        'text-cyan-',
        'bg-emerald-',
        'text-emerald-',
        'bg-amber-',
        'text-amber-',
        'bg-sky-',
        'text-sky-',
        'bg-blue-',
        'text-blue-',
        'bg-orange-',
        'text-orange-',
    )
    for token in forbidden_identity_palette_tokens:
        assert token not in asset_card


def test_inventory_snapshot_icons_are_brand_identity_while_status_remains_semantic() -> None:
    freshness = read('app/templates/inventory/kubernetes/components/_data_freshness.html')
    snapshot = read('app/templates/components/snapshot_context_bar.html')

    assert "metric_icon_palette='brand'" in freshness
    assert "icon_palette='brand'" in snapshot
    assert "'text-kaori-primary' if icon_palette == 'brand'" in snapshot
    assert 'table_label.status_label(status, tone' in snapshot
    assert 'coverage_tone' in snapshot
    assert 'exceptions_tone' in snapshot


def test_inventory_overview_shared_identity_surfaces_remain_kaori_violet() -> None:
    section_card = read('app/templates/components/operational_section_card.html')
    table = read('app/templates/components/table.html')
    drawer = read('app/templates/components/side_drawer.html')

    for template in (section_card, table, drawer):
        assert 'bg-kaori-soft text-kaori-primary' in template
