"""Committed request metadata and approval inbox read model for Protected Secret Reveal.

No Secret values or live Kubernetes provider operations. The original Reveal
service owns request, approval, reveal mutations and audit transactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import current_app
from sqlalchemy import and_, case, func, or_

from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window, paginate_query, pagination_payload
from app.kubernetes.operations.secrets.reveal_policy import (
    REVEAL_NAMESPACE_POLICIES,
    cluster_reveal_readiness,
    get_configured_enabled_namespace_names,
)
from app.models import Cluster, SecretRevealNamespacePolicy, SecretRevealRequest


def _now() -> datetime:
    return datetime.now(UTC)


def _global_enabled() -> bool:
    return bool(current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False))


def _cluster_ready(cluster: Cluster) -> bool:
    return cluster_reveal_readiness(cluster)


def get_reveal_clusters() -> list[Cluster]:
    if not _global_enabled():
        return []
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    return [
        cluster
        for cluster in clusters
        if _cluster_ready(cluster) and get_configured_enabled_namespace_names(cluster.id)
    ]


@dataclass(frozen=True, slots=True)
class PendingRevealPagination:
    page: int = 1
    per_page: int = 5


def get_reveal_page_context(
    *,
    user_id: int,
    can_approve: bool,
    my_page: int = 1,
    my_per_page: int = 5,
    my_search: str = '',
    my_status: str = '',
    my_sort: str = 'newest',
    my_request_id: str = '',
    pending_pagination: PendingRevealPagination = PendingRevealPagination(),
    pending_search: str = '',
    pending_sort: str = 'oldest',
) -> dict[str, Any]:
    now = _now()
    effective_status = case(
        (
            and_(
                SecretRevealRequest.status.in_(('pending', 'approved')),
                SecretRevealRequest.expires_at <= now,
            ),
            'expired',
        ),
        else_=SecretRevealRequest.status,
    )
    # Restrict to the requester first; filtering is SQL-backed and never reads Secret values.
    search = str(my_search or '').strip()[:120]
    allowed_statuses = {'pending', 'approved', 'revealed', 'denied', 'expired'}
    state_filter = str(my_status or '').strip().lower()
    if state_filter not in allowed_statuses:
        state_filter = ''
    ordering = 'oldest' if my_sort == 'oldest' else 'newest'

    # Exact linked-request selection is strictly scoped to the current requester.
    # Notification IDs never convey authority or permit another user's request reads.
    focus_id = str(my_request_id or '').strip()[:80]
    my_query = SecretRevealRequest.query.filter_by(requester_user_id=user_id)
    if focus_id:
        my_query = my_query.filter(SecretRevealRequest.id == focus_id)
    if search:
        search_term = search.lower()
        my_query = my_query.filter(
            or_(
                func.lower(SecretRevealRequest.secret_name).contains(search_term, autoescape=True),
                func.lower(SecretRevealRequest.key_name).contains(search_term, autoescape=True),
                func.lower(SecretRevealRequest.namespace).contains(search_term, autoescape=True),
                func.lower(SecretRevealRequest.ticket_reference).contains(search_term, autoescape=True),
            )
        )
    if state_filter:
        my_query = my_query.filter(effective_status == state_filter)
    if ordering == 'oldest':
        my_query = my_query.order_by(SecretRevealRequest.requested_at.asc(), SecretRevealRequest.id.asc())
    else:
        my_query = my_query.order_by(SecretRevealRequest.requested_at.desc(), SecretRevealRequest.id.desc())
    my_requests, my_window = paginate_query(my_query, page=my_page, per_page=my_per_page)
    # Preserve the existing Reveal template keys without keeping a separate
    # page-size policy or a second hand-written pagination algorithm.
    my_pagination = {
        **my_window,
        'total': my_window['total_items'],
        'pages': my_window['total_pages'],
        'start': my_window['start_item'],
        'end': my_window['end_item'],
        'page_sizes': PER_PAGE_OPTIONS,
    }

    # The approval permission boundary precedes all searches/pagination.
    # Only request metadata is queried; never Secret payloads.
    pending_search_value = str(pending_search or '').strip()[:120]
    pending_ordering = 'newest' if pending_sort == 'newest' else 'oldest'
    pending_requests: list[SecretRevealRequest] = []
    if can_approve:
        pending_query = SecretRevealRequest.query.filter(
            SecretRevealRequest.status == 'pending',
            SecretRevealRequest.expires_at > now,
        )
        if pending_search_value:
            pending_term = pending_search_value.lower()
            pending_query = pending_query.filter(
                or_(
                    func.lower(SecretRevealRequest.secret_name).contains(pending_term, autoescape=True),
                    func.lower(SecretRevealRequest.namespace).contains(pending_term, autoescape=True),
                    func.lower(SecretRevealRequest.key_name).contains(pending_term, autoescape=True),
                    func.lower(SecretRevealRequest.ticket_reference).contains(pending_term, autoescape=True),
                )
            )
        if pending_ordering == 'newest':
            pending_query = pending_query.order_by(
                SecretRevealRequest.requested_at.desc(), SecretRevealRequest.id.desc()
            )
        else:
            pending_query = pending_query.order_by(SecretRevealRequest.requested_at.asc(), SecretRevealRequest.id.asc())
        pending_requests, pending_window = paginate_query(
            pending_query,
            page=pending_pagination.page,
            per_page=pending_pagination.per_page,
        )
    else:
        pending_window = pagination_payload(
            build_pagination_window(
                total_items=0,
                page=pending_pagination.page,
                per_page=pending_pagination.per_page,
            )
        )
    pending_pagination_payload = {
        **pending_window,
        'total': pending_window['total_items'],
        'pages': pending_window['total_pages'],
        'start': pending_window['start_item'],
        'end': pending_window['end_item'],
        'page_sizes': PER_PAGE_OPTIONS,
    }
    configured_reveal_namespace_count = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
    ).count()

    return {
        'global_reveal_enabled': _global_enabled(),
        'configured_reveal_namespace_count': configured_reveal_namespace_count,
        'clusters': get_reveal_clusters(),
        'my_reveal_requests': my_requests,
        'my_reveal_pagination': my_pagination,
        'my_reveal_filters': {'search': search, 'status': state_filter, 'sort': ordering},
        'my_reveal_focus_id': focus_id,
        'pending_reveal_requests': pending_requests,
        'pending_reveal_pagination': pending_pagination_payload,
        'pending_reveal_filters': {'search': pending_search_value, 'sort': pending_ordering},
        'reveal_policies': REVEAL_NAMESPACE_POLICIES,
        'reveal_window_seconds': int(current_app.config.get('KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS', 15)),
    }
