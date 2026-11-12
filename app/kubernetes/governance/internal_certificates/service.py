from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy.orm import selectinload

from app.models.cluster import Cluster

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
    """Present registered, committed cluster metadata; never probe PKI or providers.

    Internal certificate expiry/health is unknown until a source-qualified worker
    writes evidence through the future #4443 collector. Connection metadata is
    NOT proof that kubeadm, a certificate or a host-side PKI source is available.
    """
    selected_cluster_id = str(args.get('cluster_id') or '').strip()
    page = _page_number(args.get('page'))
    per_page = _per_page(args.get('per_page'))
    search = str(args.get('search') or '').strip()[:100]
    query = Cluster.query.options(selectinload(Cluster.kubernetes_connection))
    if search:
        query = query.filter(Cluster.name.ilike(f'%{search}%'))
    if selected_cluster_id:
        query = query.filter(Cluster.id == selected_cluster_id)
    total_items = query.count()
    total_pages = max(ceil(total_items / per_page), 1)
    page = min(page, total_pages)
    records = query.order_by(Cluster.name.asc(), Cluster.id.asc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    clusters = [
        {
            'id': cluster.id,
            'name': cluster.name,
            'environment': cluster.environment,
            'connection_platform': (
                cluster.kubernetes_connection.detected_platform
                if cluster.kubernetes_connection and cluster.kubernetes_connection.detected_platform
                else None
            ),
            'connection_version': (
                cluster.kubernetes_connection.detected_version
                if cluster.kubernetes_connection and cluster.kubernetes_connection.detected_version
                else None
            ),
            'collection_status': 'Not Collected',
            'authority_status': 'Not Verified',
            'expiry_status': 'Unknown',
        }
        for cluster in records
    ]

    return {
        'records': clusters,
        'selected_cluster_id': selected_cluster_id,
        'search': search,
        'registered_total': Cluster.query.count(),
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
