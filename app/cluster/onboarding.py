from __future__ import annotations

from typing import Any

from flask import request
from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.cluster import Cluster

_OPERATIONAL_BLUEPRINTS = {
    'alertmanager',
    'analytics',
    'cluster',
    'dashboard',
    'governance',
    'intelligence',
    'inventory',
    'prometheus',
    'reports',
}

_BANNER_EXCLUDED_ENDPOINTS = {
    'cluster.add_cluster',
}


def build_cluster_onboarding_context() -> dict[str, Any]:
    """Return one shared cluster availability and onboarding state."""
    if not current_user.is_authenticated:
        return _hidden_context()

    try:
        cluster_count = (
            db.session.scalar(
                select(func.count(Cluster.id)),
            )
            or 0
        )
    except SQLAlchemyError:
        db.session.rollback()
        return _hidden_context(database_ready=False)

    has_clusters = cluster_count > 0
    is_operational_page = request.blueprint in _OPERATIONAL_BLUEPRINTS

    return {
        'show_banner': (
            is_operational_page and not has_clusters and request.endpoint not in _BANNER_EXCLUDED_ENDPOINTS
        ),
        'has_clusters': has_clusters,
        'cluster_count': cluster_count,
        'can_manage_clusters': current_user.has_permission('clusters.manage'),
        'database_ready': True,
    }


def _hidden_context(*, database_ready: bool = True) -> dict[str, Any]:
    return {
        'show_banner': False,
        'has_clusters': False,
        'cluster_count': 0,
        'can_manage_clusters': False,
        'database_ready': database_ready,
    }
