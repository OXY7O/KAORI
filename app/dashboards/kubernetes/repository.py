from __future__ import annotations

from importlib import import_module
from typing import Any

from sqlalchemy import func

try:
    from app.extensions.db import db
except Exception:  # pragma: no cover
    try:
        from app.extensions.db import db  # type: ignore[no-redef]
    except Exception:
        db = None  # type: ignore[assignment]


def load_models() -> dict[str, Any]:
    model_specs = {
        'Cluster': (('app.models.cluster', 'Cluster'), ('app.models', 'Cluster')),
        'NodeInventory': (('app.models.inventory', 'NodeInventory'), ('app.models', 'NodeInventory')),
        'NamespaceInventory': (('app.models.inventory', 'NamespaceInventory'), ('app.models', 'NamespaceInventory')),
        'WorkloadInventory': (('app.models.inventory', 'WorkloadInventory'), ('app.models', 'WorkloadInventory')),
        'PodInventory': (('app.models.inventory', 'PodInventory'), ('app.models', 'PodInventory')),
        'ServiceInventory': (('app.models.inventory', 'ServiceInventory'), ('app.models', 'ServiceInventory')),
        'IngressInventory': (('app.models.inventory', 'IngressInventory'), ('app.models', 'IngressInventory')),
        'StorageInventory': (('app.models.inventory', 'StorageInventory'), ('app.models', 'StorageInventory')),
        'GeneratedReport': (('app.models.report', 'Report'), ('app.models', 'Report')),
        'ReportTemplate': (('app.models.report', 'ReportTemplate'), ('app.models', 'ReportTemplate')),
        'ReportSchedule': (('app.models.report', 'ReportSchedule'), ('app.models', 'ReportSchedule')),
    }

    loaded: dict[str, Any] = {}
    for public_name, candidates in model_specs.items():
        for module_name, attr_name in candidates:
            try:
                module = import_module(module_name)
                loaded[public_name] = getattr(module, attr_name)
                break
            except Exception:
                continue
    return loaded


def query_all(model: Any, cluster_id: str | None = None, limit: int | None = None) -> list[Any]:
    if model is None:
        return []

    try:
        query = db.session.query(model) if db is not None else model.query

        if cluster_id and hasattr(model, 'cluster_id'):
            query = query.filter(getattr(model, 'cluster_id') == cluster_id)

        order_col = _first_model_column(
            model, ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check']
        )
        if order_col is not None:
            query = query.order_by(order_col.desc())

        if limit is not None:
            query = query.limit(limit)

        return list(query.all())
    except Exception:
        return []


def query_for_clusters(model: Any, cluster_ids: list[str]) -> list[Any]:
    if model is None or not cluster_ids or not hasattr(model, 'cluster_id'):
        return []

    try:
        query = db.session.query(model) if db is not None else model.query
        query = query.filter(getattr(model, 'cluster_id').in_(cluster_ids))
        order_col = _first_model_column(
            model, ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check']
        )
        if order_col is not None:
            query = query.order_by(order_col.desc())
        return list(query.all())
    except Exception:
        return []


def count_records(model: Any, cluster_id: str | None = None) -> int:
    if model is None:
        return 0
    try:
        query = db.session.query(model) if db is not None else model.query
        if cluster_id and hasattr(model, 'cluster_id'):
            query = query.filter(getattr(model, 'cluster_id') == cluster_id)
        return int(query.count())
    except Exception:
        return 0


def count_records_with_values(
    model: Any,
    column_name: str,
    values: set[str],
    cluster_id: str | None = None,
) -> int:
    if model is None or not values or not hasattr(model, column_name):
        return 0
    try:
        query = db.session.query(model) if db is not None else model.query
        if cluster_id and hasattr(model, 'cluster_id'):
            query = query.filter(getattr(model, 'cluster_id') == cluster_id)
        column = getattr(model, column_name)
        query = query.filter(func.lower(column).in_({value.lower() for value in values}))
        return int(query.count())
    except Exception:
        return 0


def latest_record_timestamp(model: Any, cluster_id: str | None = None) -> Any | None:
    if model is None:
        return None
    try:
        timestamp_column = _first_model_column(
            model, ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check']
        )
        if timestamp_column is None:
            return None
        query = db.session.query(func.max(timestamp_column)) if db is not None else model.query.with_entities(
            func.max(timestamp_column)
        )
        if cluster_id and hasattr(model, 'cluster_id'):
            query = query.filter(getattr(model, 'cluster_id') == cluster_id)
        return query.scalar()
    except Exception:
        return None


def _first_model_column(model: Any, names: list[str]) -> Any | None:
    for name in names:
        if hasattr(model, name):
            return getattr(model, name)
    return None
