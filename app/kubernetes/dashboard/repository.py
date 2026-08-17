from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db


def _query(model: Any):
    query = db.session.query(model)
    if hasattr(model, 'cluster_id') and hasattr(model, 'collected_at'):
        query = filter_current_generation(query, model)
    return query


def query_all(model: Any, cluster_id: str | None = None, limit: int | None = None) -> list[Any]:
    query = _query(model)

    if cluster_id and hasattr(model, 'cluster_id'):
        query = query.filter(getattr(model, 'cluster_id') == cluster_id)

    order_col = _first_model_column(
        model,
        ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check'],
    )
    if order_col is not None:
        query = query.order_by(order_col.desc())

    if limit is not None:
        query = query.limit(limit)

    return list(query.all())


def query_for_clusters(model: Any, cluster_ids: list[str]) -> list[Any]:
    if not cluster_ids or not hasattr(model, 'cluster_id'):
        return []

    query = _query(model).filter(getattr(model, 'cluster_id').in_(cluster_ids))
    order_col = _first_model_column(
        model,
        ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check'],
    )
    if order_col is not None:
        query = query.order_by(order_col.desc())
    return list(query.all())


def count_records(model: Any, cluster_id: str | None = None) -> int:
    query = _query(model)
    if cluster_id and hasattr(model, 'cluster_id'):
        query = query.filter(getattr(model, 'cluster_id') == cluster_id)
    return int(query.count())


def count_records_with_values(
    model: Any,
    column_name: str,
    values: set[str],
    cluster_id: str | None = None,
) -> int:
    if not values or not hasattr(model, column_name):
        return 0

    query = _query(model)
    if cluster_id and hasattr(model, 'cluster_id'):
        query = query.filter(getattr(model, 'cluster_id') == cluster_id)
    column = getattr(model, column_name)
    query = query.filter(func.lower(column).in_({value.lower() for value in values}))
    return int(query.count())


def latest_record_timestamp(model: Any, cluster_id: str | None = None) -> Any | None:
    timestamp_column = _first_model_column(
        model,
        ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check'],
    )
    if timestamp_column is None:
        return None

    query = _query(model).with_entities(func.max(timestamp_column))
    if cluster_id and hasattr(model, 'cluster_id'):
        query = query.filter(getattr(model, 'cluster_id') == cluster_id)
    return query.scalar()


def _first_model_column(model: Any, names: list[str]) -> Any | None:
    for name in names:
        if hasattr(model, name):
            return getattr(model, name)
    return None
