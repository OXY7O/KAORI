from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KPI_CARDS = ROOT / 'app/templates/inventory/overview/partials/_kpi_cards.html'
ASSET_CARD = ROOT / 'app/templates/components/inventory_asset_card.html'
SECTION_CARD = ROOT / 'app/templates/components/operational_section_card.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_inventory_overview_asset_catalog_uses_shared_section_and_destination_cards() -> None:
    template = read(KPI_CARDS)

    assert 'components/operational_section_card.html' in template
    assert 'components/inventory_asset_card.html' in template
    assert "'Inventory Asset Catalog'" in template
    assert 'overview.asset_catalog' in template
    assert 'url_for(asset.endpoint)' in template
    assert 'progress_bar.html' not in template
    assert 'Collection Coverage' not in template
    assert 'Healthy Targets' not in template


def test_inventory_asset_card_owns_catalog_geometry_and_typography() -> None:
    asset_card = read(ASSET_CARD)
    section_card = read(SECTION_CARD)

    assert 'rounded-xl border border-outline-default bg-surface-card' in asset_card
    assert 'text-base font-semibold text-content-primary' in asset_card
    assert 'text-xs leading-5 text-content-muted' in asset_card
    assert 'Open Inventory' in asset_card
    assert 'text-base font-semibold text-content-primary' in section_card
