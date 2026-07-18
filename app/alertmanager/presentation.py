from __future__ import annotations

from typing import Any

from app.alertmanager.repository import count_bindings_by_scope_type, list_instances
from app.alertmanager.sanitization import safe_endpoint
from app.extensions import db
from app.models.alertmanager import AlertmanagerBinding, AlertmanagerInstance
from app.models.cluster import Cluster


def build_inventory_context(
    *,
    query: str = '',
    readiness: str = '',
    deployment_type: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    instances = list_instances()
    rows = [_instance_row(instance) for instance in instances]
    filtered = rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered = [
            row
            for row in filtered
            if normalized_query in row['search_text']
        ]
    if readiness:
        filtered = [row for row in filtered if row['readiness'] == readiness]
    if deployment_type:
        filtered = [row for row in filtered if row['deployment_type'] == deployment_type]

    page_rows, pagination = _paginate(filtered, page=page, per_page=per_page)
    stats = {
        'total': len(rows),
        'configured': sum(1 for row in rows if row['configured']),
        'ready': sum(1 for row in rows if row['readiness'] == 'ready'),
        'attention': sum(1 for row in rows if row['configured'] and row['readiness'] != 'ready'),
        'bindings': sum(row['binding_count'] for row in rows),
    }
    return {
        'rows': page_rows,
        'stats': stats,
        'pagination': pagination,
        'selected_query': query,
        'selected_readiness': readiness,
        'selected_deployment_type': deployment_type,
        'readiness_options': sorted({row['readiness'] for row in rows}),
        'deployment_type_options': sorted({row['deployment_type'] for row in rows}),
        'binding_scope_counts': count_bindings_by_scope_type(),
    }


def build_instance_context(instance: AlertmanagerInstance | None = None) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    return {
        'instance': instance,
        'bindings': list(instance.bindings) if instance is not None else [],
        'binding_rows': [_binding_row(binding) for binding in instance.bindings] if instance else [],
        'clusters': clusters,
        'stats': {
            'bindings': len(instance.bindings) if instance else 0,
            'ready': bool(instance and instance.readiness_status == 'ready'),
            'capabilities': len(instance.capabilities or []) if instance else 0,
        },
    }


def _instance_row(instance: AlertmanagerInstance) -> dict[str, Any]:
    readiness = instance.readiness_status or ('validation_required' if instance.endpoint else 'not_configured')
    return {
        'instance': instance,
        'configured': bool(instance.endpoint),
        'endpoint': safe_endpoint(instance.endpoint),
        'version': instance.detected_version,
        'compatibility': instance.compatibility_status or 'validation_required',
        'readiness': readiness,
        'profile': instance.compatibility_profile,
        'deployment_type': instance.deployment_type,
        'binding_count': len(instance.bindings),
        'scope_types': sorted({binding.scope_type for binding in instance.bindings if binding.enabled}),
        'search_text': ' '.join(
            filter(
                None,
                [
                    instance.name.lower(),
                    (instance.description or '').lower(),
                    instance.endpoint.lower(),
                    instance.deployment_type.lower(),
                ],
            )
        ),
    }


def _binding_row(binding: AlertmanagerBinding) -> dict[str, Any]:
    label = binding.scope_key
    if binding.scope_type == 'kubernetes_cluster':
        cluster = db.session.get(Cluster, binding.scope_key)
        if cluster is not None:
            label = cluster.name
    return {
        'binding': binding,
        'scope_label': label,
        'scope_type_label': binding.scope_type.replace('_', ' ').title(),
    }


def _paginate(
    rows: list[dict[str, Any]],
    *,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = [5, 10, 25, 50]
    if per_page not in allowed:
        per_page = 5
    total_items = len(rows)
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    return rows[start:end], {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start + 1 if total_items else 0,
        'end_item': min(end, total_items),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed,
    }
