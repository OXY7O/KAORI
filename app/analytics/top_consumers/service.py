from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from app.analytics.common.coercion import safe_float, safe_int
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import ALLOWED_PER_PAGE_VALUES
from app.analytics.top_consumers.contracts import (
    FOCUS_FILTER_OPTIONS,
    PRIORITY_OPTIONS,
    RESOURCE_OPTIONS,
    TopConsumersSelection,
    get_selected_tab,
    get_sort_options,
)
from app.analytics.top_consumers.domain import (
    build_top_consumers_payload,
    empty_payload,
    is_current_payload,
)
from app.analytics.top_consumers.evidence import (
    TOP_CONSUMERS_ADVISORY_CAPABILITIES,
    TopConsumersEvidenceCollector,
    metric_label,
    sample_metric,
)
from app.analytics.top_consumers.presentation import (
    apply_record_presentation,
    attach_recommendations,
)
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_connection_blocker


class TopConsumersSnapshot(TypedDict):
    cpu: list[dict[str, Any]]
    memory: list[dict[str, Any]]
    storage: list[dict[str, Any]]
    pods: list[dict[str, Any]]
    recommendation_count: int


class TopConsumersService:
    """Orchestrate one committed Top Consumers snapshot."""

    def __init__(self, utilization_service: UtilizationService) -> None:
        self.utilization_service = utilization_service
        self.collector = TopConsumersEvidenceCollector(
            utilization_service.consumer
        )

    def get_prometheus_status(self) -> dict[str, Any]:
        return self.utilization_service.get_prometheus_status()

    def get_top_consumers_payload(
        self,
        selection: TopConsumersSelection,
    ) -> dict[str, Any]:
        requirements = self.collector.consumer.requirements(
            TOP_CONSUMERS_ADVISORY_CAPABILITIES
        )
        advisory_missing = frozenset(
            str(value)
            for value in (
                (requirements.payload or {}).get(
                    'advisory_missing_capabilities',
                    (),
                )
            )
            if value
        )
        evidence = self.collector.collect(
            namespace=selection.namespace,
            advisory_missing=advisory_missing,
        )
        payload = build_top_consumers_payload(
            evidence=evidence,
            selected_namespace=selection.namespace,
        )
        payload['namespace_options'] = sorted(
            {
                metric_label(sample_metric(item), 'namespace')
                for item in evidence.namespaces.rows
                if metric_label(sample_metric(item), 'namespace')
            }
        )
        payload, _ = apply_record_presentation(
            payload=payload,
            query_args={
                'resource': selection.resource,
                'search': selection.search,
                'sort': selection.sort,
                'priority': selection.priority,
                'focus': selection.focus,
                'page': selection.page,
                'per_page': selection.per_page,
            },
        )
        return attach_recommendations(payload)


def get_top_consumers_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
    )
    selection = TopConsumersSelection.from_mapping(query_args)
    context.update(
        {
            'selected_namespace': selection.namespace,
            'selected_resource': selection.resource,
            'selected_time_range': 'current',
            'selected_search': selection.search,
            'selected_focus': selection.focus,
            'selected_priority': selection.priority,
            'selected_sort': selection.sort,
            'initial_tab': get_selected_tab(query_args),
            'resource_options': RESOURCE_OPTIONS,
            'priority_options': PRIORITY_OPTIONS,
            'focus_options': FOCUS_FILTER_OPTIONS,
            'sort_options': get_sort_options(selection.resource),
            'allowed_time_ranges': (),
            'allowed_per_page_values': ALLOWED_PER_PAGE_VALUES,
            'namespace_options': (
                [selection.namespace] if selection.namespace else []
            ),
            'consumer_payload': empty_payload(
                message='No cluster available. Add a Kubernetes cluster first.',
                page=selection.page,
                per_page=selection.per_page,
            ),
        }
    )
    if utilization_service is None or cluster is None:
        return context

    top_consumers_service = TopConsumersService(utilization_service)
    prometheus_status = top_consumers_service.get_prometheus_status()
    context['prometheus_status'] = prometheus_status
    context['prometheus_connected'] = bool(
        prometheus_status.get('connected', False)
    )
    if not context['prometheus_connected']:
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=safe_message(
                value=prometheus_status.get('error'),
                default=(
                    'Prometheus health check did not complete successfully.'
                ),
            ),
        )
        context['consumer_payload'] = empty_payload(
            message=safe_message(
                value=prometheus_status.get('error'),
                default=(
                    'Prometheus is not connected for the selected cluster.'
                ),
            ),
            page=selection.page,
            per_page=selection.per_page,
        )
        return context

    consumer_payload = top_consumers_service.get_top_consumers_payload(selection)
    namespace_options = list(consumer_payload.get('namespace_options') or [])
    if selection.namespace:
        namespace_options = sorted({*namespace_options, selection.namespace})
    context['namespace_options'] = namespace_options
    context['consumer_payload'] = consumer_payload
    return context


def get_top_consumers_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> TopConsumersSnapshot | None:
    del time_range
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.top_consumers',
        parameters={'cluster_id': str(cluster_id)},
    )
    payload = (
        (result.context or {}).get('consumer_payload')
        if result.available
        else None
    )
    if not is_current_payload(payload):
        return None
    rows = list(payload.get('all_rows') or [])
    return {
        'cpu': build_snapshot_items(
            rows=[row for row in rows if row.get('resource_type') == 'cpu'],
            limit=5,
        ),
        'memory': build_snapshot_items(
            rows=[
                row for row in rows if row.get('resource_type') == 'memory'
            ],
            limit=5,
        ),
        'storage': build_snapshot_items(
            rows=[row for row in rows if row.get('resource_type') == 'pvc'],
            limit=5,
        ),
        'pods': build_snapshot_items(
            rows=[row for row in rows if row.get('resource_type') == 'pods'],
            limit=5,
        ),
        'recommendation_count': safe_int(
            payload.get('recommendation_count', 0)
        ),
    }


def build_snapshot_items(
    *,
    rows: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    top_rows = sorted(
        rows,
        key=lambda row: safe_float(row.get('current_usage', 0)),
        reverse=True,
    )[:limit]
    max_value = max(
        [safe_float(row.get('current_usage', 0)) for row in top_rows],
        default=0,
    )
    items: list[dict[str, Any]] = []
    for row in top_rows:
        identity = (
            row.get('identity')
            if isinstance(row.get('identity'), dict)
            else {}
        )
        namespace = str(row.get('namespace') or '')
        primary = str(
            identity.get('primary')
            or row.get('workload')
            or row.get('pod')
            or row.get('pvc_name')
            or '-'
        )
        pressure = row.get('pressure_percent')
        contribution = row.get('contribution_percent')
        semantic_percent = (
            safe_float(pressure)
            if pressure is not None
            else safe_float(contribution)
            if contribution is not None
            else None
        )
        raw_value = safe_float(row.get('current_usage', 0))
        items.append(
            {
                'name': primary,
                'namespace': namespace,
                'pod': str(row.get('pod') or ''),
                'container': str(row.get('container') or ''),
                'workload': str(
                    row.get('workload_owner') or row.get('workload') or ''
                ),
                'identity': {
                    'primary': primary,
                    'secondary': str(identity.get('secondary') or namespace),
                    'tertiary': str(identity.get('tertiary') or ''),
                },
                'value': str(row.get('current_display') or 'N/A'),
                'raw_value': raw_value,
                'percent': (
                    safe_int(semantic_percent)
                    if semantic_percent is not None
                    else None
                ),
                'bar_percent': relative_percent(raw_value, max_value),
                'pressure_percent': pressure,
                'contribution_percent': contribution,
                'risk': row.get('risk', {}),
                'recommendation': str(row.get('recommendation') or ''),
            }
        )
    return items


def relative_percent(value: float, total: float) -> int:
    if total <= 0:
        return 0
    return safe_int(min(100.0, value / total * 100))


def safe_message(*, value: Any, default: str) -> str:
    if isinstance(value, str) and value:
        return value
    return default if value is None else str(value)
