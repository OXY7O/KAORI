from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import func, select

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.kubernetes import KubernetesConnection

_DEFAULT_PER_PAGE = 5
_PER_PAGE_OPTIONS = (5, 10, 25, 50)


def _page_number(raw: Any) -> int:
    try:
        return min(max(int(raw or 1), 1), 10000)
    except (TypeError, ValueError):
        return 1


def _per_page(raw: Any) -> int:
    try:
        parsed = int(raw or _DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        return _DEFAULT_PER_PAGE
    return parsed if parsed in _PER_PAGE_OPTIONS else _DEFAULT_PER_PAGE


def get_internal_certificates_source_page(args: Any) -> dict[str, Any]:
    """Read only non-secret committed registration fields; never probe PKI.

    Internal certificate expiry and health remain unreported until a qualified
    collector commits actual evidence in the independent #4443 workstream.
    Explicit column projections never load/decrypt KubernetesConnection.kubeconfig.
    """
    selected_cluster_id = str(args.get('cluster_id') or '').strip()
    search = str(args.get('search') or '').strip()[:100]
    page = _page_number(args.get('page'))
    per_page = _per_page(args.get('per_page'))

    count_stmt = select(func.count(Cluster.id))
    stmt = (
        select(
            Cluster.id,
            Cluster.name,
            Cluster.environment,
            KubernetesConnection.detected_platform,
            KubernetesConnection.detected_version,
        )
        .select_from(Cluster)
        .outerjoin(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
    )
    if selected_cluster_id:
        count_stmt = count_stmt.where(Cluster.id == selected_cluster_id)
        stmt = stmt.where(Cluster.id == selected_cluster_id)
    if search:
        count_stmt = count_stmt.where(Cluster.name.ilike(f'%{search}%'))
        stmt = stmt.where(Cluster.name.ilike(f'%{search}%'))

    total_items = db.session.scalar(count_stmt) or 0
    total_pages = max(ceil(total_items / per_page), 1)
    page = min(page, total_pages)
    rows = db.session.execute(
        stmt.order_by(Cluster.name.asc(), Cluster.id.asc()).offset((page - 1) * per_page).limit(per_page)
    ).all()

    records = [
        {
            'id': row.id,
            'name': row.name,
            'environment': row.environment,
            'connection_platform': row.detected_platform,
            'connection_version': row.detected_version,
            'collection_status': 'Not Collected',
            'authority_status': 'Not Verified',
            'expiry_status': 'Unknown',
        }
        for row in rows
    ]

    return {
        'records': records,
        'selected_cluster_id': selected_cluster_id,
        'search': search,
        'registered_total': db.session.scalar(select(func.count(Cluster.id))) or 0,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'allowed_per_page': _PER_PAGE_OPTIONS,
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': (page - 1) * per_page + 1 if total_items else 0,
            'end_item': min(page * per_page, total_items),
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': max(page - 1, 1),
            'next_page': min(page + 1, total_pages),
        },
        'status': 'Not Collected',
        'source_authority': 'Not Verified',
        'renewal_state': 'Monitor Only',
    }
