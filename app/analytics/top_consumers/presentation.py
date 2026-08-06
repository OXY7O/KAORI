from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.coercion import safe_float
from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_per_page_arg,
    get_positive_int_arg,
    get_query_value,
)
from app.analytics.top_consumers.contracts import (
    FOCUS_FILTER_OPTIONS,
    PRIORITY_OPTIONS,
    RESOURCE_OPTIONS,
    RISK_RANK,
    get_selected_focus,
    get_selected_priority,
    get_selected_resource,
    get_selected_sort,
    get_selected_tab,
    get_sort_options,
)
from app.analytics.top_consumers.domain import (
    dominant_namespace_names,
    empty_payload,
    is_current_payload,
)
from app.analytics.top_consumers.recommendations import (
    build_top_consumers_actionable_recommendations,
)
from app.intelligence.recommendation_engine import (
    count_actionable_recommendations,
    format_recommendation_cards,
)


def filter_rows(
    *,
    rows: list[dict[str, Any]],
    selected_search: str,
    selected_resource: str,
    selected_priority: str,
    selected_focus: str,
) -> list[dict[str, Any]]:
    dominant_namespaces = set(dominant_namespace_names(rows))
    filtered: list[dict[str, Any]] = []
    normalized_search = selected_search.lower().strip()
    for row in rows:
        resource_type = str(row.get('resource_type') or '')
        risk_key = str((row.get('risk') or {}).get('key') or 'unknown')
        request = safe_float(row.get('request', 0))
        pressure = row.get('pressure_percent')
        namespace = str(row.get('namespace') or '')
        if selected_focus == 'missing_requests' and not (
            resource_type in {'cpu', 'memory'}
            and row.get('request_evidence_available') is True
            and request <= 0
        ):
            continue
        if selected_focus == 'high_usage' and not (
            resource_type in {'cpu', 'memory'}
            and pressure is not None
            and safe_float(pressure) >= 75
        ):
            continue
        if (
            selected_focus == 'dominant_namespaces'
            and namespace not in dominant_namespaces
        ):
            continue
        if selected_focus == 'high_pvc' and not (
            resource_type == 'pvc'
            and pressure is not None
            and safe_float(pressure) >= 80
        ):
            continue
        if selected_resource != 'all' and resource_type != selected_resource:
            continue
        if selected_priority and risk_key != selected_priority:
            continue
        if normalized_search and normalized_search not in search_haystack(row):
            continue
        filtered.append(row)
    return filtered


def search_haystack(row: dict[str, Any]) -> str:
    identity = row.get('identity') if isinstance(row.get('identity'), dict) else {}
    values = (
        row.get('namespace', ''),
        identity.get('primary', ''),
        identity.get('secondary', ''),
        identity.get('tertiary', ''),
        row.get('pod', ''),
        row.get('container', ''),
        row.get('pvc_name', ''),
        row.get('resource_label', ''),
        row.get('recommendation', ''),
    )
    return ' '.join(str(value) for value in values).lower()


def sort_rows(
    *,
    rows: list[dict[str, Any]],
    selected_sort: str,
    selected_resource: str,
) -> list[dict[str, Any]]:
    if selected_sort == 'absolute' and selected_resource != 'all':
        return sorted(
            rows,
            key=lambda row: safe_float(row.get('current_usage', 0)),
            reverse=True,
        )
    if selected_sort == 'pressure' and selected_resource != 'all':
        return sorted(
            rows,
            key=lambda row: optional_metric_sort_key(row.get('pressure_percent')),
            reverse=True,
        )
    if selected_sort == 'contribution':
        return sorted(
            rows,
            key=lambda row: optional_metric_sort_key(
                row.get('contribution_percent')
            ),
            reverse=True,
        )
    if selected_sort == 'namespace':
        return sorted(
            rows,
            key=lambda row: (
                str(row.get('namespace', '')),
                str(row.get('resource_type', '')),
            ),
        )
    if selected_sort == 'resource':
        return sorted(
            rows,
            key=lambda row: (
                str(row.get('resource_type', '')),
                -optional_metric_sort_key(
                    row.get('contribution_percent')
                )[1],
            ),
        )
    return sorted(
        rows,
        key=lambda row: (
            RISK_RANK.get(
                str((row.get('risk') or {}).get('key') or 'unknown'),
                0,
            ),
            optional_metric_sort_key(row.get('pressure_percent')),
            optional_metric_sort_key(row.get('contribution_percent')),
        ),
        reverse=True,
    )


def optional_metric_sort_key(value: Any) -> tuple[int, float]:
    if value is None:
        return (0, 0.0)
    return (1, safe_float(value))


def apply_record_presentation(
    *,
    payload: dict[str, Any],
    query_args: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_resource = get_selected_resource(query_args)
    selected_search = get_query_value(
        query_args=query_args,
        name='search',
        default='',
    )
    selected_priority = get_selected_priority(query_args)
    selected_focus = get_selected_focus(query_args)
    selected_sort = get_selected_sort(query_args, selected_resource)
    page = get_positive_int_arg(query_args=query_args, name='page', default=1)
    per_page = get_per_page_arg(
        query_args=query_args,
        name='per_page',
        default=5,
    )
    all_rows = list(payload.get('all_rows') or [])
    filtered = filter_rows(
        rows=all_rows,
        selected_search=selected_search,
        selected_resource=selected_resource,
        selected_priority=selected_priority,
        selected_focus=selected_focus,
    )
    sorted_records = sort_rows(
        rows=filtered,
        selected_sort=selected_sort,
        selected_resource=selected_resource,
    )
    ranked = [
        dict(row, rank=index)
        for index, row in enumerate(sorted_records, start=1)
    ]
    page_payload = AnalyticsBaseService().paginate_rows_with_options(
        rows=ranked,
        page=page,
        per_page=per_page,
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )
    presented = deepcopy(payload)
    presented.update(
        {
            'has_data': bool(all_rows),
            'rows': page_payload['rows'],
            'pagination': page_payload['pagination'],
            'total_rows': len(filtered),
            'scope_total_rows': len(all_rows),
        }
    )
    controls = {
        'selected_resource': selected_resource,
        'selected_search': selected_search,
        'selected_priority': selected_priority,
        'selected_focus': selected_focus,
        'selected_sort': selected_sort,
        'initial_tab': get_selected_tab(query_args),
        'resource_options': RESOURCE_OPTIONS,
        'priority_options': PRIORITY_OPTIONS,
        'focus_options': FOCUS_FILTER_OPTIONS,
        'sort_options': get_sort_options(selected_resource),
        'allowed_per_page_values': ALLOWED_PER_PAGE_VALUES,
    }
    return presented, controls


def attach_recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    recommendations = build_top_consumers_actionable_recommendations(payload)
    cards = format_recommendation_cards(
        recommendations,
        default_title='Review Top Consumers',
        default_description=(
            'Review CPU, memory, pod, and PVC consumer hotspots.'
        ),
        default_source='top_consumers',
        default_action_type='consumer_review',
    )
    payload.update(
        {
            'actionable_recommendations': recommendations,
            'recommendation_cards': cards,
            'recommendation_count': count_actionable_recommendations(
                recommendations
            ),
            'recommendations': cards,
        }
    )
    return payload


def present_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    presented = deepcopy(context)
    selected_namespace = get_query_value(
        query_args=query_args,
        name='namespace',
        default='',
    )
    payload = deepcopy(presented.get('consumer_payload') or {})
    page = get_positive_int_arg(query_args=query_args, name='page', default=1)
    per_page = get_per_page_arg(
        query_args=query_args,
        name='per_page',
        default=5,
    )
    if not is_current_payload(payload):
        payload = empty_payload(
            message=(
                'The committed Top Consumers snapshot uses an earlier payload '
                'schema. Run Refresh/Materialize Top Consumers to rebuild the '
                'snapshot before reviewing consumer evidence.'
            ),
            page=page,
            per_page=per_page,
        )
        payload['snapshot_schema_outdated'] = True
        payload['scope'] = {
            'label': (
                f'Namespace · {selected_namespace}'
                if selected_namespace
                else 'Cluster'
            ),
            'namespace': selected_namespace,
            'snapshot_dimension': 'namespace' if selected_namespace else 'cluster',
        }
    snapshot_namespace = str((payload.get('scope') or {}).get('namespace') or '')
    if selected_namespace and snapshot_namespace != selected_namespace:
        payload = empty_payload(
            message=(
                'The committed snapshot does not match the requested Namespace. '
                'Run Refresh/Materialize Top Consumers for this Namespace before '
                'reviewing consumer evidence.'
            ),
            page=page,
            per_page=per_page,
        )
        payload['scope'] = {
            'label': f'Namespace · {selected_namespace}',
            'namespace': selected_namespace,
            'snapshot_dimension': 'namespace',
        }
        payload['snapshot_scope_mismatch'] = True
    elif snapshot_namespace:
        selected_namespace = snapshot_namespace
    namespace_options = sorted(
        {
            *[str(value) for value in presented.get('namespace_options') or []],
            *([selected_namespace] if selected_namespace else []),
        }
    )
    payload, controls = apply_record_presentation(
        payload=payload,
        query_args=query_args,
    )
    attach_recommendations(payload)
    presented.update(
        {
            **controls,
            'selected_namespace': selected_namespace,
            'selected_time_range': 'current',
            'allowed_time_ranges': (),
            'namespace_options': namespace_options,
            'consumer_payload': payload,
        }
    )
    return presented
