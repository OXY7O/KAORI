from sqlalchemy import select

from app.inventory.resources.common import filter_current_generation
from app.models import NodeInventory


def test_current_generation_filter_uses_cluster_generation_marker() -> None:
    statement = filter_current_generation(select(NodeInventory), NodeInventory)
    sql = str(statement.compile(compile_kwargs={'literal_binds': True})).lower()

    assert 'cluster_inventory' in sql
    assert 'node_inventory.collected_at' in sql
    assert 'cluster_inventory.collected_at' in sql
    assert 'cluster_inventory.cluster_id = node_inventory.cluster_id' in sql
