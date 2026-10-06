from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.platform_operations.global_search.service import navigation_results, resource_results, strip_internal_score

bp = Blueprint('global_search', __name__, url_prefix='/search')


@bp.get('/global')
@login_required
def global_search():
    query = request.args.get('q', '', type=str).strip()[:120]
    current_cluster_id = request.args.get('cluster_id', '', type=str).strip()[:64]
    has_permission = current_user.has_permission

    resources = resource_results(
        query=query,
        current_cluster_id=current_cluster_id,
        can_view_kubernetes_inventory=has_permission('inventory.view'),
        can_view_object_storage_inventory=has_permission('object_storage_inventory.view'),
    )
    navigation = navigation_results(query=query, has_permission=has_permission)

    sections = []
    if resources:
        sections.append({'key': 'resources', 'label': 'Resources', 'items': strip_internal_score(resources)})
    if navigation:
        sections.append(
            {
                'key': 'navigation',
                'label': 'Navigation' if query else 'Quick navigation',
                'items': strip_internal_score(navigation),
            }
        )

    return jsonify(
        {
            'query': query,
            'minimum_resource_query_length': 2,
            'sections': sections,
        }
    )
