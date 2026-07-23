from pathlib import Path


def test_recommendation_engine_uses_inventory_generation_boundary() -> None:
    source = Path('app/intelligence/service.py').read_text()

    assert 'from app.common.inventory_generation import filter_current_generation' in source
    assert 'filter_current_generation(db.session.query(PodInventory), PodInventory)' in source
    assert 'filter_current_generation(unhealthy_query, PodInventory)' in source
    assert 'filter_current_generation(restart_query, PodInventory)' in source
    assert 'filter_current_generation(query, NodeInventory)' in source
    assert 'filter_current_generation(query, StorageInventory)' in source


def test_generation_filter_remains_owned_by_neutral_inventory_boundary() -> None:
    source = Path('app/common/inventory_generation.py').read_text()

    assert 'ClusterInventory.collected_at' in source
    assert 'model.collected_at == generation' in source
