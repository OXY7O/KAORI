from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.params import ALLOWED_PER_PAGE_VALUES, get_query_value
from app.analytics.storage.domain import (
    build_storage_posture,
    summarize_filesystem,
    summarize_pv,
    summarize_pvc,
)
from app.analytics.storage.pagination import resolve_storage_pagination
from app.intelligence.recommendation_engine import (
    build_storage_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)

STORAGE_TABS = ('capacity', 'filesystem', 'pvc', 'pv', 'recommendations')


@dataclass(frozen=True, slots=True)
class StorageViewState:
    namespace: str
    node: str
    tab: str
    pvc_search: str
    pvc_status: str
    pvc_storage_class: str
    pv_search: str
    pv_status: str
    pv_storage_class: str
    pagination: dict[str, dict[str, int]]

    @classmethod
    def from_query(cls, query_args: Mapping[str, Any]) -> StorageViewState:
        return cls(
            namespace=get_query_value(
                query_args=query_args,
                name='namespace',
                default='',
            ),
            node=get_query_value(
                query_args=query_args,
                name='storage_node',
                default='',
            ),
            tab=get_selected_storage_tab(query_args),
            pvc_search=get_query_value(
                query_args=query_args,
                name='pvc_search',
                default='',
            ),
            pvc_status=get_query_value(
                query_args=query_args,
                name='pvc_status',
                default='',
            ),
            pvc_storage_class=get_query_value(
                query_args=query_args,
                name='pvc_storage_class',
                default='',
            ),
            pv_search=get_query_value(
                query_args=query_args,
                name='pv_search',
                default='',
            ),
            pv_status=get_query_value(
                query_args=query_args,
                name='pv_status',
                default='',
            ),
            pv_storage_class=get_query_value(
                query_args=query_args,
                name='pv_storage_class',
                default='',
            ),
            pagination=resolve_storage_pagination(
                query_args,
                allowed_per_page=ALLOWED_PER_PAGE_VALUES,
                default_per_page=5,
            ),
        )


def get_selected_storage_tab(
    query_args: Mapping[str, Any],
    *,
    default: str = 'capacity',
) -> str:
    selected = get_query_value(
        query_args=query_args,
        name='tab',
        default=default,
    )
    return selected if selected in STORAGE_TABS else default


def present_storage_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply local scope, filters, and pagination to one committed snapshot."""
    presented = deepcopy(context)
    view = StorageViewState.from_query(query_args)
    namespace_options = [
        str(value)
        for value in presented.get('namespace_options', [])
        if str(value)
    ]
    selected_namespace = (
        view.namespace if not view.namespace or view.namespace in namespace_options else ''
    )

    storage_summary = deepcopy(presented.get('storage_summary') or {})
    node_filesystem = deepcopy(storage_summary.get('node_filesystem') or {})
    persistent = deepcopy(storage_summary.get('persistent_storage') or {})

    node_filesystem, selected_node = _present_filesystem(
        node_filesystem,
        selected_node=view.node,
        pagination=view.pagination['filesystem'],
    )
    persistent = _present_persistent_storage(
        persistent,
        selected_namespace=selected_namespace,
        view=view,
    )
    storage_summary['node_filesystem'] = node_filesystem
    storage_summary['persistent_storage'] = persistent

    posture = build_storage_posture(
        node_filesystem.get('summary') or {},
        persistent.get('pvc') or {},
        persistent.get('pv') or {},
    )
    recommendations = build_storage_actionable_recommendations(
        {'storage_summary': storage_summary}
    )

    presented.update(
        {
            'selected_namespace': selected_namespace,
            'selected_time_range': 'current',
            'allowed_time_ranges': (),
            'selected_storage_node': selected_node,
            'selected_storage_tab': view.tab,
            'initial_tab': view.tab,
            'selected_pvc_search': view.pvc_search,
            'selected_pvc_status': view.pvc_status,
            'selected_pvc_storage_class': view.pvc_storage_class,
            'selected_pv_search': view.pv_search,
            'selected_pv_status': view.pv_status,
            'selected_pv_storage_class': view.pv_storage_class,
            'storage_summary': storage_summary,
            'storage_posture': posture,
            'storage_pressure_lanes': _pressure_lanes(storage_summary),
            'actionable_recommendations': recommendations,
            'recommendation_cards': format_recommendation_cards(
                recommendations,
                include_presentation_classes=False,
            ),
            'recommendation_count': count_actionable_recommendations(
                recommendations
            ),
        }
    )
    return presented


def _present_filesystem(
    node_filesystem: dict[str, Any],
    *,
    selected_node: str,
    pagination: dict[str, int],
) -> tuple[dict[str, Any], str]:
    all_rows = list(
        node_filesystem.get('all_rows') or node_filesystem.get('rows') or []
    )
    available_nodes = sorted(
        {
            str(row.get('node') or '')
            for row in all_rows
            if str(row.get('node') or '')
        }
        | {
            str(value)
            for value in node_filesystem.get('available_nodes', [])
            if str(value)
        }
    )
    if selected_node and selected_node not in available_nodes:
        selected_node = ''
    scoped_rows = [
        row
        for row in all_rows
        if not selected_node or str(row.get('node') or '') == selected_node
    ]
    page = _paginate(scoped_rows, pagination)
    node_filesystem.update(
        {
            'all_rows': all_rows,
            'available_nodes': available_nodes,
            'selected_node': selected_node,
            'scope_label': selected_node or 'All Nodes',
            'summary': summarize_filesystem(
                scoped_rows,
                query_observed=bool(node_filesystem.get('query_observed')),
            ),
            'rows': page['rows'],
            'pagination': page['pagination'],
        }
    )
    return node_filesystem, selected_node


def _present_persistent_storage(
    persistent: dict[str, Any],
    *,
    selected_namespace: str,
    view: StorageViewState,
) -> dict[str, Any]:
    cluster_pvc_rows = list(
        persistent.get('pvc_all_rows') or persistent.get('pvc_rows') or []
    )
    pv_all_rows = list(
        persistent.get('pv_all_rows') or persistent.get('pv_rows') or []
    )
    scoped_pvc_rows = [
        row
        for row in cluster_pvc_rows
        if not selected_namespace
        or str(row.get('namespace') or '') == selected_namespace
    ]
    pvc_filtered = filter_storage_rows(
        scoped_pvc_rows,
        search=view.pvc_search,
        status=view.pvc_status,
        storage_class=view.pvc_storage_class,
    )
    pv_filtered = filter_storage_rows(
        pv_all_rows,
        search=view.pv_search,
        status=view.pv_status,
        storage_class=view.pv_storage_class,
    )
    pvc_page = _paginate(pvc_filtered, view.pagination['pvc'])
    pv_page = _paginate(pv_filtered, view.pagination['pv'])
    pvc_inventory_observed = bool(persistent.get('pvc_inventory_observed'))
    pvc_status_observed = bool(persistent.get('pvc_status_observed'))
    pv_inventory_observed = bool(persistent.get('pv_inventory_observed'))
    pv_status_observed = bool(persistent.get('pv_status_observed'))

    persistent.update(
        {
            'pvc': summarize_pvc(
                scoped_pvc_rows,
                inventory_observed=pvc_inventory_observed,
                status_observed=pvc_status_observed,
                scope_label=(
                    f'Namespace · {selected_namespace}'
                    if selected_namespace
                    else 'All Namespaces'
                ),
            ),
            'pv': summarize_pv(
                pv_all_rows,
                inventory_observed=pv_inventory_observed,
                status_observed=pv_status_observed,
                claim_rows=cluster_pvc_rows,
                claim_inventory_observed=pvc_inventory_observed,
            ),
            'pvc_all_rows': scoped_pvc_rows,
            'pvc_rows': pvc_page['rows'],
            'pvc_pagination': pvc_page['pagination'],
            'pvc_selected_search': view.pvc_search,
            'pvc_selected_status': view.pvc_status,
            'pvc_selected_storage_class': view.pvc_storage_class,
            'pvc_status_options': unique_options(scoped_pvc_rows, 'status'),
            'pvc_storage_class_options': unique_options(
                scoped_pvc_rows,
                'storage_class',
            ),
            'pv_all_rows': pv_all_rows,
            'pv_rows': pv_page['rows'],
            'pv_pagination': pv_page['pagination'],
            'pv_selected_search': view.pv_search,
            'pv_selected_status': view.pv_status,
            'pv_selected_storage_class': view.pv_storage_class,
            'pv_status_options': unique_options(pv_all_rows, 'status'),
            'pv_storage_class_options': unique_options(
                pv_all_rows,
                'storage_class',
            ),
        }
    )
    return persistent


def filter_storage_rows(
    rows: list[dict[str, Any]],
    *,
    search: str = '',
    status: str = '',
    storage_class: str = '',
) -> list[dict[str, Any]]:
    normalized_search = search.strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if normalized_search:
            haystack = ' '.join(
                str(row.get(key) or '')
                for key in (
                    'name',
                    'namespace',
                    'claim',
                    'volume_name',
                    'storage_class',
                    'reclaim_policy',
                )
            ).lower()
            if normalized_search not in haystack:
                continue
        if status and str(row.get('status') or '') != status:
            continue
        if storage_class and str(row.get('storage_class') or '') != storage_class:
            continue
        filtered.append(row)
    return filtered


def unique_options(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted(
        {
            str(row.get(key) or '')
            for row in rows
            if str(row.get(key) or '')
        }
    )


def _paginate(
    rows: list[dict[str, Any]],
    state: dict[str, int],
) -> dict[str, Any]:
    return AnalyticsBaseService().paginate_rows_with_options(
        rows=rows,
        page=int(state.get('page') or 1),
        per_page=int(state.get('per_page') or 5),
        allowed_per_page=list(ALLOWED_PER_PAGE_VALUES),
        default_per_page=5,
    )


def _pressure_lanes(storage_summary: dict[str, Any]) -> list[dict[str, Any]]:
    filesystem = (storage_summary.get('node_filesystem') or {}).get('summary') or {}
    persistent = storage_summary.get('persistent_storage') or {}
    pvc = persistent.get('pvc') or {}
    pvc_scope = str(pvc.get('scope_label') or 'All Namespaces')
    pvc_coverage = str(pvc.get('pressure_coverage_display') or 'N/A')
    pvc_complete = bool(pvc.get('pressure_evidence_complete'))
    pvc_reason = (
        'Observed claim usage is measured against paired observed volume capacity. '
        + (
            'Coverage is complete for the active scope.'
            if pvc_complete
            else 'The aggregate excludes claims without paired kubelet volume statistics.'
        )
    )
    return [
        {
            'label': 'Node Filesystem',
            'icon': 'server',
            'value': filesystem.get('usage_percent'),
            'used_capacity': f"{filesystem.get('used', 'N/A')} / {filesystem.get('capacity', 'N/A')}",
            'description': 'Scope: '
            + str((storage_summary.get('node_filesystem') or {}).get('scope_label') or 'All Nodes'),
            'tone': (filesystem.get('risk') or {}).get('tone', 'unknown'),
            'status_label': (filesystem.get('risk') or {}).get('label', 'Unknown'),
            'reason': (
                f"Highest pressure is {float(filesystem['highest_usage']):.1f}% "
                f"on {filesystem.get('highest_node') or '-'}"
                if filesystem.get('highest_usage') is not None
                else ''
            ),
            'headroom': filesystem.get('free_percent'),
            'available': bool(filesystem.get('evidence_available')),
        },
        {
            'label': 'PVC Volume Usage',
            'icon': 'box',
            'value': pvc.get('used_percent'),
            'used_capacity': (
                f"{pvc.get('pressure_used', 'N/A')} / "
                f"{pvc.get('pressure_capacity', 'N/A')}"
            ),
            'description': (
                f'Scope: {pvc_scope}'
                + (f' · Coverage: {pvc_coverage}' if pvc_coverage != 'N/A' else '')
            ),
            'tone': (pvc.get('risk') or {}).get('tone', 'unknown'),
            'status_label': (pvc.get('risk') or {}).get('label', 'Unknown'),
            'reason': pvc_reason,
            'headroom': pvc.get('free_percent'),
            'available': bool(pvc.get('pressure_evidence_available')),
        },
    ]
