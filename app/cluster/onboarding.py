from __future__ import annotations

from typing import Any

from flask import g, request
from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.cluster import Cluster

_KUBERNETES_SCOPE_BLUEPRINTS = {
    'analytics',
    'cluster',
    'kubernetes_dashboard',
    'governance',
    'inventory',
    'kubernetes_operations',
}

_BANNER_EXCLUDED_ENDPOINTS = {
    'cluster.add_cluster',
    'welcome.index',
}


def get_registered_cluster_count() -> int | None:
    """Return the registered cluster count once per request.

    ``None`` means the database was not available, so callers should avoid
    treating the request as a normal zero-cluster onboarding state.
    """
    cached_count = getattr(g, 'kaori_cluster_count', None)
    if cached_count is not None:
        return int(cached_count)

    try:
        cluster_count = (
            db.session.scalar(
                select(func.count(Cluster.id)),
            )
            or 0
        )
    except SQLAlchemyError:
        db.session.rollback()
        return None

    g.kaori_cluster_count = cluster_count
    return cluster_count


def has_registered_clusters() -> bool | None:
    """Return whether a cluster exists, preserving database failure as ``None``."""
    cluster_count = get_registered_cluster_count()
    return None if cluster_count is None else cluster_count > 0


def build_cluster_onboarding_context() -> dict[str, Any]:
    """Return the shared Kubernetes scope availability and blocker state."""
    if not current_user.is_authenticated:
        return _hidden_context()

    cluster_count = get_registered_cluster_count()
    if cluster_count is None:
        return _hidden_context(database_ready=False)

    has_clusters = cluster_count > 0
    is_kubernetes_scope = request.blueprint in _KUBERNETES_SCOPE_BLUEPRINTS
    is_blocked = is_kubernetes_scope and not has_clusters and request.endpoint not in _BANNER_EXCLUDED_ENDPOINTS

    return {
        'show_banner': is_blocked,
        'is_kubernetes_scope': is_kubernetes_scope,
        'is_blocked': is_blocked,
        'has_clusters': has_clusters,
        'cluster_count': cluster_count,
        'can_manage_clusters': current_user.has_permission('clusters.manage'),
        'database_ready': True,
    }


def _hidden_context(*, database_ready: bool = True) -> dict[str, Any]:
    return {
        'show_banner': False,
        'is_kubernetes_scope': False,
        'is_blocked': False,
        'has_clusters': False,
        'cluster_count': 0,
        'can_manage_clusters': False,
        'database_ready': database_ready,
    }
