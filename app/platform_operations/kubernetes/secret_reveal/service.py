from __future__ import annotations

from math import ceil
from typing import Any

from flask import current_app

from app.common.presentation import present_user_datetime
from app.kubernetes_operations.secrets.reveal_policy import (
    REVEAL_NAMESPACE_POLICIES,
    build_namespace_policy_rows,
    cluster_reveal_readiness_evidence,
)
from app.models import Cluster, SecretRevealNamespacePolicy

_NAMESPACE_DEFAULT_PER_PAGE = 5
_NAMESPACE_PER_PAGE_OPTIONS = (_NAMESPACE_DEFAULT_PER_PAGE, 10, 25, 50)
_NAMESPACE_POLICY_FILTERS = {
    'all': 'All policies',
    'enabled': 'Enabled only',
    'disabled': 'Disabled',
    'step_up': 'Step-up authentication',
    'approval_required': 'Approval required',
    'missing': 'Missing from live cluster',
    'unknown': 'Live state unknown',
}


def _normalize_page(value: str | int | None) -> int:
    try:
        return max(int(value or 1), 1)
    except (TypeError, ValueError):
        return 1


def _normalize_per_page(value: str | int | None) -> int:
    try:
        per_page = int(value or _NAMESPACE_DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = _NAMESPACE_DEFAULT_PER_PAGE
    if per_page not in _NAMESPACE_PER_PAGE_OPTIONS:
        return _NAMESPACE_DEFAULT_PER_PAGE
    return per_page


def _normalize_policy_filter(value: str | None) -> str:
    normalized = (value or 'all').strip().lower()
    if normalized not in _NAMESPACE_POLICY_FILTERS:
        return 'all'
    return normalized


def _filter_namespace_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    policy_filter: str,
) -> list[dict[str, Any]]:
    filtered_rows = rows
    if query:
        filtered_rows = [row for row in filtered_rows if query in row['namespace'].lower()]

    if policy_filter == 'enabled':
        return [row for row in filtered_rows if row['policy'] in {'step_up', 'approval_required'}]
    if policy_filter == 'missing':
        return [row for row in filtered_rows if row['live_state'] == 'missing']
    if policy_filter == 'unknown':
        return [row for row in filtered_rows if row['live_state'] == 'unknown']
    if policy_filter != 'all':
        return [row for row in filtered_rows if row['policy'] == policy_filter]
    return filtered_rows


def build_secret_reveal_settings_context(
    selected_cluster_id: str | None,
    *,
    namespace_query: str | None = None,
    namespace_policy_filter: str | None = None,
    page: str | int | None = None,
    per_page: str | int | None = None,
    refresh_namespace_source: bool = False,
) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    selected_cluster = None
    normalized_cluster_id = (selected_cluster_id or '').strip()

    if normalized_cluster_id:
        selected_cluster = next(
            (cluster for cluster in clusters if cluster.id == normalized_cluster_id),
            None,
        )
    elif clusters:
        selected_cluster = clusters[0]

    all_namespace_rows: list[dict[str, Any]] = []
    namespace_source = None
    selected_cluster_readiness = {
        'credential_configured': False,
        'encryption_verified': False,
        'audit_verified': False,
        'ready': False,
    }
    if selected_cluster is not None:
        all_namespace_rows, namespace_source = build_namespace_policy_rows(
            selected_cluster,
            refresh_source=refresh_namespace_source,
        )
        selected_cluster_readiness = cluster_reveal_readiness_evidence(selected_cluster)

    normalized_query = (namespace_query or '').strip().lower()
    normalized_policy_filter = _normalize_policy_filter(namespace_policy_filter)
    normalized_per_page = _normalize_per_page(per_page)
    requested_page = _normalize_page(page)

    filtered_namespace_rows = _filter_namespace_rows(
        all_namespace_rows,
        query=normalized_query,
        policy_filter=normalized_policy_filter,
    )
    filtered_total = len(filtered_namespace_rows)
    total_pages = max(ceil(filtered_total / normalized_per_page), 1)
    current_page = min(requested_page, total_pages)
    start_offset = (current_page - 1) * normalized_per_page
    namespace_rows = filtered_namespace_rows[start_offset : start_offset + normalized_per_page]
    start_item = start_offset + 1 if filtered_total else 0
    end_item = min(start_offset + normalized_per_page, filtered_total)

    total_enabled_namespaces = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
    ).count()
    protected_cluster_count = (
        SecretRevealNamespacePolicy.query.with_entities(SecretRevealNamespacePolicy.cluster_id)
        .filter(SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required')))
        .distinct()
        .count()
    )

    selected_enabled_namespace_count = sum(
        row['policy'] in {'step_up', 'approval_required'} for row in all_namespace_rows
    )

    namespace_source_context = {
        'state': namespace_source.state if namespace_source is not None else 'unavailable',
        'available': bool(namespace_source is not None and namespace_source.available),
        'last_attempted_at': (
            present_user_datetime(namespace_source.last_attempted_at, empty='Not attempted')
            if namespace_source is not None
            else 'Not attempted'
        ),
        'last_successful_at': (
            present_user_datetime(namespace_source.last_successful_at, empty='No successful refresh')
            if namespace_source is not None
            else 'No successful refresh'
        ),
        'has_successful_snapshot': bool(
            namespace_source is not None and namespace_source.last_successful_at is not None
        ),
    }

    return {
        'clusters': clusters,
        'selected_cluster': selected_cluster,
        'namespace_rows': namespace_rows,
        'namespace_filters': {
            'query': (namespace_query or '').strip(),
            'policy': normalized_policy_filter,
            'per_page': normalized_per_page,
        },
        'namespace_filter_options': _NAMESPACE_POLICY_FILTERS,
        'namespace_per_page_options': _NAMESPACE_PER_PAGE_OPTIONS,
        'namespace_pagination': {
            'page': current_page,
            'per_page': normalized_per_page,
            'total_items': filtered_total,
            'total_pages': total_pages,
            'start_item': start_item,
            'end_item': end_item,
            'has_prev': current_page > 1,
            'has_next': current_page < total_pages,
            'prev_page': max(current_page - 1, 1),
            'next_page': min(current_page + 1, total_pages),
        },
        'namespace_summary': {
            'total': len(all_namespace_rows),
            'enabled': selected_enabled_namespace_count,
            'disabled': sum(row['policy'] == 'disabled' for row in all_namespace_rows),
            'missing': sum(row['live_state'] == 'missing' for row in all_namespace_rows),
            'unknown': sum(row['live_state'] == 'unknown' for row in all_namespace_rows),
        },
        'namespace_source': namespace_source_context,
        'reveal_policy_choices': REVEAL_NAMESPACE_POLICIES,
        'global_reveal_enabled': bool(current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False)),
        'selected_cluster_readiness': selected_cluster_readiness,
        'selected_cluster_ready': bool(selected_cluster_readiness['ready']),
        'protected_cluster_count': protected_cluster_count,
        'total_enabled_namespaces': total_enabled_namespaces,
        'selected_enabled_namespace_count': selected_enabled_namespace_count,
    }
