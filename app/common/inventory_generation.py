from __future__ import annotations

from sqlalchemy import select

from app.models import ClusterInventory


def filter_current_generation(query, model):
    """Limit inventory rows to the committed generation marker for each cluster."""
    generation = (
        select(ClusterInventory.collected_at)
        .where(ClusterInventory.cluster_id == model.cluster_id)
        .scalar_subquery()
    )
    return query.filter(model.collected_at == generation)
