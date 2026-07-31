from __future__ import annotations

from typing import Any, SupportsFloat, SupportsIndex

MAX_DASHBOARD_RECOMMENDATIONS = 5


def build_dashboard_recommendations(
    *,
    selected_cluster_id: str | None = None,
    limit: int = MAX_DASHBOARD_RECOMMENDATIONS,
) -> list[dict[str, Any]]:
    """Return active findings produced by the central Intelligence engine.

    Dashboard does not define or evaluate its own recommendation rules. The
    returned items are the same catalog-backed findings used by
    Intelligence > Recommendations, optionally scoped to the selected cluster.
    """

    from app.intelligence.service import get_active_recommendation_findings

    return get_active_recommendation_findings(
        selected_cluster_id=selected_cluster_id,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# CENTRALIZED ANALYTICS RECOMMENDATION HELPERS
# ---------------------------------------------------------------------------
# Shared recommendation helpers for analytics domains.
# Keep this module framework-neutral so it can be reused by PDF renderers,
# analytics UI payloads, and future report summary counters.

SIGNAL_PRIORITIES = {
    'critical': 'Critical',
    'warning': 'Warning',
    'warn': 'Warning',
    'high': 'Warning',
    'medium': 'Warning',
    'low': 'Info',
    'normal': 'Normal',
    'healthy': 'Normal',
    'ok': 'Normal',
    'info': 'Info',
}

PRIORITY_STYLES = {
    'Critical': {
        'icon_class': 'bg-red-100 text-red-600 dark:bg-red-500/10 dark:text-red-300',
        'priority_class': 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-300',
    },
    'Warning': {
        'icon_class': 'bg-amber-100 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
        'priority_class': 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
    },
    'Normal': {
        'icon_class': 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300',
        'priority_class': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
    },
    'Info': {
        'icon_class': 'bg-blue-100 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300',
        'priority_class': 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300',
    },
}

SOURCE_LABELS = {
    'capacity': 'Capacity Analysis',
    'capacity_risk': 'Capacity Risk',
    'capacity_headroom': 'Capacity Headroom',
    'capacity_governance': 'Capacity Governance',
    'capacity_baseline': 'Capacity Baseline',
    'capacity_practice': 'Capacity Practice',
    'utilization': 'Utilization',
    'utilization_risk': 'Utilization Risk',
    'top_consumers': 'Top Consumers',
    'top_consumers_missing_requests': 'Top Consumers Missing Requests',
    'top_consumers_high_usage': 'Top Consumers High Usage',
    'top_consumers_dominant_namespaces': 'Top Consumers Dominant Namespaces',
    'top_consumers_high_pvc': 'Top Consumers High PVC',
    'top_consumers_baseline': 'Top Consumers Baseline',
    'top_consumers_practice': 'Top Consumers Practice',
    'top_cpu_consumer': 'Top CPU Consumer',
    'top_memory_consumer': 'Top Memory Consumer',
    'storage': 'Storage Analysis',
    'storage_filesystem': 'Filesystem Storage',
    'storage_pvc': 'Persistent Volume Claim',
    'storage_pv': 'Persistent Volume',
    'storage_baseline': 'Storage Baseline',
    'storage_practice': 'Storage Practice',
    'workload': 'Workload Analysis',
    'workload_quota': 'Tenant Quota',
    'workload_resource_mapping': 'Workload Resource Mapping',
    'workload_rightsizing': 'Workload Right-Sizing',
    'workload_governance': 'Workload Governance',
    'workload_baseline': 'Workload Baseline',
    'workload_practice': 'Workload Practice',
    'forecast': 'Resource Forecast',
    'forecast_projection': 'Forecast Projection',
    'forecast_eta': 'Forecast Threshold ETA',
    'forecast_growth': 'Forecast Growth Trend',
    'forecast_confidence': 'Forecast Confidence',
    'forecast_baseline': 'Forecast Baseline',
    'forecast_practice': 'Forecast Practice',
}


SOURCE_HREFS = {
    'capacity': '/analytics/capacity',
    'capacity_risk': '/analytics/capacity',
    'capacity_headroom': '/analytics/capacity',
    'capacity_governance': '/analytics/capacity',
    'capacity_baseline': '/analytics/capacity',
    'capacity_practice': '/analytics/capacity',
    'utilization': '/analytics/utilization',
    'utilization_risk': '/analytics/utilization',
    'top_consumers': '/analytics/top-consumers',
    'top_consumers_missing_requests': '/analytics/top-consumers?focus=missing_requests',
    'top_consumers_high_usage': '/analytics/top-consumers?focus=high_usage',
    'top_consumers_dominant_namespaces': '/analytics/top-consumers?focus=dominant_namespaces',
    'top_consumers_high_pvc': '/analytics/top-consumers?resource=pvc&focus=high_pvc',
    'top_consumers_baseline': '/analytics/top-consumers',
    'top_consumers_practice': '/analytics/top-consumers',
    'top_cpu_consumer': '/analytics/top-consumers',
    'top_memory_consumer': '/analytics/top-consumers',
    'storage': '/analytics/storage?tab=capacity',
    'storage_filesystem': '/analytics/storage?tab=filesystem',
    'storage_pvc': '/analytics/storage?tab=pvc',
    'storage_pv': '/analytics/storage?tab=pv',
    'storage_baseline': '/analytics/storage?tab=capacity',
    'storage_practice': '/analytics/storage?tab=capacity',
    'workload': '/analytics/workload',
    'workload_quota': '/analytics/workload',
    'workload_resource_mapping': '/analytics/workload',
    'workload_rightsizing': '/analytics/workload',
    'workload_governance': '/analytics/workload',
    'workload_baseline': '/analytics/workload',
    'workload_practice': '/analytics/workload',
    'forecast': '/analytics/forecast',
    'forecast_projection': '/analytics/forecast',
    'forecast_eta': '/analytics/forecast',
    'forecast_growth': '/analytics/forecast',
    'forecast_confidence': '/analytics/forecast',
    'forecast_baseline': '/analytics/forecast',
    'forecast_practice': '/analytics/forecast',
}


SOURCE_LABELS.update(
    {
        'alerts': 'Alerts & Anomalies',
        'alerts_source': 'Alert Source Health',
        'alerts_critical': 'Critical Alerts',
        'alerts_warning': 'Warning Alerts',
        'alerts_anomaly': 'Anomaly Signals',
        'alerts_affected_resources': 'Affected Resources',
        'alerts_baseline': 'Alert Baseline',
        'alerts_practice': 'Alert Practice',
    }
)

SOURCE_HREFS.update(
    {
        'alerts': '/analytics/alerts-anomalies',
        'alerts_source': '/analytics/alerts-anomalies',
        'alerts_critical': '/analytics/alerts-anomalies-anomalies?severity=critical',
        'alerts_warning': '/analytics/alerts-anomalies-anomalies?severity=warning',
        'alerts_anomaly': '/analytics/alerts-anomalies',
        'alerts_affected_resources': '/analytics/alerts-anomalies',
        'alerts_baseline': '/analytics/alerts-anomalies',
        'alerts_practice': '/analytics/alerts-anomalies',
    }
)

RESOURCE_ICONS = {
    'cpu': 'cpu',
    'memory': 'memory-stick',
    'storage': 'hard-drive',
    'pod': 'boxes',
    'pods': 'boxes',
    'forecast': 'line-chart',
}


def normalize_priority(
    value: Any,
    default: str = 'Info',
) -> str:
    normalized = str(value or '').strip().lower()

    return SIGNAL_PRIORITIES.get(
        normalized,
        default,
    )


def normalize_source_key(value: Any) -> str:
    return str(value or '').strip().lower().replace(' ', '_').replace('-', '_')


def format_source_label(source: Any) -> str:
    source_key = normalize_source_key(source)

    if source_key in SOURCE_LABELS:
        return SOURCE_LABELS[source_key]

    return source_key.replace('_', ' ').title() if source_key else 'Recommendation Engine'


def get_source_href(source: Any, default: str = '/analytics') -> str:
    return SOURCE_HREFS.get(
        normalize_source_key(source),
        default,
    )


def get_status_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get(
                'label',
                value.get('status', 'Unknown'),
            )
            or 'Unknown'
        )

    return str(value or 'Unknown')


def get_numeric_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_actionable_priority(priority: str) -> bool:
    return priority in {'Critical', 'Warning'}


def is_actionable_value(value: Any, priority: str) -> bool:
    if isinstance(value, bool):
        return value

    normalized = str(value or '').strip().lower()

    if normalized in {'yes', 'true', '1'}:
        return True

    if normalized in {'no', 'false', '0'}:
        return False

    return is_actionable_priority(priority)


def count_actionable_recommendations(recommendations: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in recommendations
        if is_actionable_value(
            item.get('is_actionable'),
            str(item.get('priority', '')),
        )
    )


def summarize_recommendations(recommendations: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        'total': len(recommendations),
        'actionable': count_actionable_recommendations(recommendations),
        'critical': 0,
        'warning': 0,
        'normal': 0,
        'info': 0,
    }

    for item in recommendations:
        priority = normalize_priority(
            item.get('priority', 'Info'),
            default='Info',
        )

        if priority == 'Critical':
            summary['critical'] += 1
        elif priority == 'Warning':
            summary['warning'] += 1
        elif priority == 'Normal':
            summary['normal'] += 1
        else:
            summary['info'] += 1

    return summary


def deduplicate_recommendations(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduplicated: list[dict[str, Any]] = []

    for item in recommendations:
        key = (
            str(item.get('title', '')).strip().lower(),
            str(item.get('description', '')).strip().lower(),
            str(item.get('source', '')).strip().lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        deduplicated.append(item)

    return deduplicated


def get_recommendation_icon(
    *,
    source: Any = '',
    resource: Any = '',
    action_type: Any = '',
    default: str = 'activity',
) -> str:
    resource_key = normalize_source_key(resource)
    source_key = normalize_source_key(source)
    action_key = normalize_source_key(action_type)

    if resource_key in RESOURCE_ICONS:
        return RESOURCE_ICONS[resource_key]

    if 'storage' in source_key or 'storage' in action_key:
        return 'hard-drive'

    if 'forecast' in source_key or 'forecast' in action_key or 'projection' in source_key:
        return 'line-chart'

    if 'workload' in source_key or 'governance' in source_key or 'workload' in action_key:
        return 'shield-alert'

    if 'alert' in source_key or 'alert' in action_key:
        return 'triangle-alert'

    if 'anomaly' in source_key or 'anomaly' in action_key:
        return 'radar'

    if 'consumer' in source_key or 'consumer' in action_key:
        return 'flame'

    if 'capacity' in source_key or 'capacity' in action_key:
        return 'bar-chart-3'

    if 'utilization' in source_key or 'utilization' in action_key:
        return 'activity'

    return default


def get_priority_style(priority: Any) -> dict[str, str]:
    normalized = normalize_priority(priority, default='Info')

    return PRIORITY_STYLES.get(
        normalized,
        PRIORITY_STYLES['Info'],
    )


def build_recommendation(
    title: str,
    description: str,
    priority: str,
    source: str,
    *,
    source_label: str = '',
    resource: str = '',
    action_type: str = '',
    href: str = '',
    icon: str = '',
    is_actionable: bool | None = None,
) -> dict[str, Any]:
    normalized_priority = normalize_priority(
        priority,
        default='Info',
    )
    source_key = normalize_source_key(source)
    resolved_actionable = is_actionable_priority(normalized_priority) if is_actionable is None else is_actionable
    style = get_priority_style(normalized_priority)

    return {
        'title': title,
        'description': description,
        'priority': normalized_priority,
        'source': source_key or source,
        'source_label': source_label or format_source_label(source_key or source),
        'resource': resource,
        'action_type': action_type,
        'href': href or get_source_href(source_key or source),
        'icon': icon
        or get_recommendation_icon(
            source=source_key or source,
            resource=resource,
            action_type=action_type,
        ),
        'icon_class': style['icon_class'],
        'priority_class': style['priority_class'],
        'is_actionable': 'Yes' if resolved_actionable else 'No',
    }


def format_recommendation_card(
    recommendation: dict[str, Any],
    *,
    default_title: str = 'Review recommendation',
    default_description: str = 'Review the related analytics page for operational context.',
    default_source: str = 'recommendation_engine',
    default_action_type: str = 'review',
    include_presentation_classes: bool = True,
) -> dict[str, Any]:
    if not isinstance(recommendation, dict):
        recommendation = {}

    priority = normalize_priority(
        recommendation.get('priority', 'Info'),
        default='Info',
    )
    source = str(recommendation.get('source') or default_source)
    source_label = str(recommendation.get('source_label') or format_source_label(source))
    resource = str(recommendation.get('resource') or '')
    action_type = str(recommendation.get('action_type') or default_action_type)

    card = {
        'title': str(recommendation.get('title') or recommendation.get('label') or default_title),
        'description': str(recommendation.get('description') or recommendation.get('label') or default_description),
        'priority': priority,
        'source': source,
        'source_label': source_label,
        'resource': resource,
        'action_type': action_type,
        'href': str(recommendation.get('href') or get_source_href(source)),
        'icon': str(
            recommendation.get('icon')
            or get_recommendation_icon(
                source=source,
                resource=resource,
                action_type=action_type,
            )
        ),
        'is_actionable': 'Yes' if is_actionable_value(recommendation.get('is_actionable'), priority) else 'No',
    }
    if include_presentation_classes:
        style = get_priority_style(priority)
        card.update(
            {
                'icon_class': str(recommendation.get('icon_class') or style['icon_class']),
                'priority_class': str(recommendation.get('priority_class') or style['priority_class']),
            }
        )
    return card


def format_recommendation_cards(
    recommendations: list[dict[str, Any]],
    *,
    default_title: str = 'Review recommendation',
    default_description: str = 'Review the related analytics page for operational context.',
    default_source: str = 'recommendation_engine',
    default_action_type: str = 'review',
    include_presentation_classes: bool = True,
) -> list[dict[str, Any]]:
    cards = [
        format_recommendation_card(
            recommendation,
            default_title=default_title,
            default_description=default_description,
            default_source=default_source,
            default_action_type=default_action_type,
            include_presentation_classes=include_presentation_classes,
        )
        for recommendation in recommendations
        if isinstance(recommendation, dict)
    ]

    if cards:
        return cards

    return [
        format_recommendation_card(
            {
                'title': default_title,
                'description': default_description,
                'priority': 'Info',
                'source': default_source,
                'action_type': default_action_type,
                'is_actionable': 'No',
            },
            default_title=default_title,
            default_description=default_description,
            default_source=default_source,
            default_action_type=default_action_type,
            include_presentation_classes=include_presentation_classes,
        )
    ]


def build_capacity_actionable_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    risk_summary = payload.get('risk_summary', [])

    if isinstance(risk_summary, list):
        for item in risk_summary:
            if not isinstance(item, dict):
                continue

            if item.get('evidence_available') is False:
                continue

            resource_key = str(item.get('resource') or '').lower()
            resource_label = str(item.get('label', 'Resource') or 'Resource')
            headroom = get_numeric_value(item.get('headroom', 0))
            status_label = get_status_label(item.get('status', 'Normal'))
            priority = normalize_priority(status_label, default='Info')

            if not is_actionable_priority(priority):
                continue

            recommendations.append(
                build_recommendation(
                    title=f'Review {resource_label} capacity headroom',
                    description=(
                        f'{resource_label} capacity status is {status_label} with '
                        f'{headroom:.2f}% headroom. Validate allocation, workload growth, '
                        'and near-term scheduling demand before adding more workloads.'
                    ),
                    priority=priority,
                    source='capacity_risk',
                    source_label='Capacity Risk Summary',
                    resource=resource_key,
                    action_type='capacity_review',
                    href='/analytics/capacity',
                )
            )

    capacity_summary = payload.get('capacity_summary', {})

    if isinstance(capacity_summary, dict):
        for resource_key, item in capacity_summary.items():
            if not isinstance(item, dict):
                continue
            if item.get('evidence_available') is False or get_numeric_value(item.get('capacity', 0)) <= 0:
                continue

            headroom = get_numeric_value(item.get('headroom', 0))

            if headroom <= 10:
                priority = 'Critical'
            elif headroom <= 25:
                priority = 'Warning'
            else:
                continue

            resource_label = str(resource_key).replace('_', ' ').title()

            recommendations.append(
                build_recommendation(
                    title=f'Increase {resource_label} capacity planning attention',
                    description=(
                        f'{resource_label} headroom is {headroom:.2f}%. '
                        'Review requests, limits, autoscaling policy, and upcoming deployment demand.'
                    ),
                    priority=priority,
                    source='capacity_headroom',
                    source_label='Capacity Headroom Threshold',
                    resource=str(resource_key),
                    action_type='capacity_review',
                    href='/analytics/capacity',
                )
            )

    governance_findings = payload.get('governance_findings', [])

    if isinstance(governance_findings, list):
        for item in governance_findings:
            if not isinstance(item, dict):
                continue

            severity = normalize_priority(item.get('severity', 'Info'), default='Info')

            if severity == 'Normal':
                continue

            label = str(item.get('label', 'Review capacity governance finding') or 'Review capacity governance finding')
            filter_hint = str(item.get('filter', '-') or '-')

            recommendations.append(
                build_recommendation(
                    title=label,
                    description=(
                        'Review the related workloads, namespaces, or resource policies. '
                        f'Finding filter/context: {filter_hint}.'
                    ),
                    priority=severity,
                    source='capacity_governance',
                    source_label='Capacity Governance Finding',
                    action_type='governance_review',
                    href='/analytics/capacity',
                )
            )

    recommendations = deduplicate_recommendations(recommendations)

    if recommendations:
        return recommendations

    return [
        build_recommendation(
            title='Continue Monitoring Schedulable Capacity',
            description=(
                'No actionable capacity pressure was detected from current risk summary and governance findings. '
                'Continue watching worker capacity, allocation trend, and upcoming workload demand.'
            ),
            priority='Normal',
            source='capacity_baseline',
            source_label='Capacity Baseline',
            action_type='capacity_review',
            href='/analytics/capacity',
            is_actionable=False,
        ),
        build_recommendation(
            title='Review Capacity After Major Deployments',
            description=(
                'Re-run Capacity Analysis after large deployments, scaling events, or node pool changes '
                'to validate that headroom remains safe.'
            ),
            priority='Info',
            source='capacity_practice',
            source_label='Capacity Operating Practice',
            action_type='capacity_review',
            href='/analytics/capacity',
            is_actionable=False,
        ),
    ]


def build_utilization_actionable_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    risk_assessment = payload.get('risk_assessment', {})

    if isinstance(risk_assessment, dict):
        for resource_key in ['cpu', 'memory', 'storage', 'pods']:
            item = risk_assessment.get(resource_key, {})

            if not isinstance(item, dict):
                continue

            status_label = get_status_label(item.get('status', 'Normal'))
            priority = normalize_priority(status_label, default='Info')

            if not is_actionable_priority(priority):
                continue

            utilization = get_numeric_value(item.get('utilization', 0))
            pressure_nodes = str(item.get('pressure_nodes', 0) or 0)
            reason = str(item.get('reason', '-') or '-')
            resource_label = resource_key.upper()

            recommendations.append(
                build_recommendation(
                    title=f'Review {resource_label} utilization pressure',
                    description=(
                        f'{resource_label} status is {status_label} with utilization around '
                        f'{utilization:.2f}%. Pressure nodes: {pressure_nodes}. Reason: {reason}. '
                        'Validate whether requests, limits, replicas, or capacity need adjustment.'
                    ),
                    priority=priority,
                    source='utilization_risk',
                    source_label='Utilization Risk Assessment',
                    resource=resource_key,
                    action_type='utilization_review',
                    href='/analytics/utilization',
                )
            )

    top_cpu_consumers = payload.get('top_cpu_consumers', [])
    top_memory_consumers = payload.get('top_memory_consumers', [])

    if isinstance(top_cpu_consumers, list) and top_cpu_consumers:
        top_item = top_cpu_consumers[0]

        if isinstance(top_item, dict):
            recommendations.append(
                build_recommendation(
                    title='Review Top CPU Consumer',
                    description=(
                        'Validate whether the highest CPU consumer is expected. '
                        f'Namespace: {top_item.get("namespace", "-")}; pod: {top_item.get("pod", "-")}; '
                        f'value: {top_item.get("value", "-")}.'
                    ),
                    priority='Info',
                    source='top_cpu_consumer',
                    source_label='Top CPU Consumer',
                    resource='cpu',
                    action_type='top_consumer_review',
                    href='/analytics/top-consumers',
                    is_actionable=False,
                )
            )

    if isinstance(top_memory_consumers, list) and top_memory_consumers:
        top_item = top_memory_consumers[0]

        if isinstance(top_item, dict):
            recommendations.append(
                build_recommendation(
                    title='Review Top Memory Consumer',
                    description=(
                        'Validate whether the highest memory consumer is expected. '
                        f'Namespace: {top_item.get("namespace", "-")}; pod: {top_item.get("pod", "-")}; '
                        f'value: {top_item.get("value", "-")}.'
                    ),
                    priority='Info',
                    source='top_memory_consumer',
                    source_label='Top Memory Consumer',
                    resource='memory',
                    action_type='top_consumer_review',
                    href='/analytics/top-consumers',
                    is_actionable=False,
                )
            )

    recommendations = deduplicate_recommendations(recommendations)

    if recommendations:
        return recommendations

    return [
        build_recommendation(
            title='Continue Regular Utilization Monitoring',
            description=(
                'No actionable utilization pressure was detected from current risk assessment. '
                'Continue tracking CPU, memory, storage, pod usage, and recurring consumer hotspots.'
            ),
            priority='Normal',
            source='utilization',
            source_label='Utilization Baseline',
            action_type='utilization_review',
            href='/analytics/utilization',
            is_actionable=False,
        ),
        build_recommendation(
            title='Validate Workload Resource Requests and Limits Periodically',
            description=(
                'Even when utilization is healthy, review requests and limits regularly to prevent '
                'over-allocation, under-allocation, and noisy-neighbor risk.'
            ),
            priority='Info',
            source='utilization',
            source_label='Utilization Operating Practice',
            action_type='workload_review',
            href='/analytics/workload',
            is_actionable=False,
        ),
    ]


STORAGE_ACTIONABLE_RISK_LABELS = {
    'warning',
    'watch',
    'high',
    'critical',
    'lost',
    'pending',
    'failed',
    'unknown',
}


def build_storage_actionable_recommendations(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    storage_summary = payload.get('storage_summary', payload)

    if not isinstance(storage_summary, dict):
        storage_summary = {}

    node_filesystem = storage_summary.get('node_filesystem', {})
    persistent_storage = storage_summary.get('persistent_storage', {})

    if not isinstance(node_filesystem, dict):
        node_filesystem = {}

    if not isinstance(persistent_storage, dict):
        persistent_storage = {}

    filesystem_summary = node_filesystem.get('summary', {})

    if not isinstance(filesystem_summary, dict):
        filesystem_summary = {}

    filesystem_rows = _as_list(node_filesystem.get('all_rows') or node_filesystem.get('rows', []))
    pvc_rows = _as_list(persistent_storage.get('pvc_all_rows') or persistent_storage.get('pvc_rows', []))
    pv_rows = _as_list(persistent_storage.get('pv_all_rows') or persistent_storage.get('pv_rows', []))

    highest_filesystem_usage = get_numeric_value(
        filesystem_summary.get('highest_usage', filesystem_summary.get('usage_percent', 0)),
    )
    highest_node = str(filesystem_summary.get('highest_node', '-') or '-')

    if highest_filesystem_usage >= 90:
        priority = 'Critical'
    elif highest_filesystem_usage >= 75:
        priority = 'Warning'
    else:
        priority = ''

    if priority:
        recommendations.append(
            build_recommendation(
                title='Review Node Filesystem Pressure',
                description=(
                    f'Highest /var filesystem usage is {highest_filesystem_usage:.2f}% on {highest_node}. '
                    'Review image growth, logs, ephemeral storage consumption, and node cleanup before scheduling more workloads.'
                ),
                priority=priority,
                source='storage_filesystem',
                source_label='Filesystem Storage',
                resource='storage',
                action_type='storage_review',
                href='/analytics/storage?tab=filesystem',
            )
        )

    fs_risk_count = _count_rows_by_risk_label(
        filesystem_rows,
        {'watch', 'high', 'critical'},
    )

    if fs_risk_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review Filesystem Risk Items',
                description=(
                    f'{fs_risk_count} filesystem row(s) have Watch, High, or Critical risk. '
                    'Prioritize nodes with high /var usage before image pulls, log growth, or workload placement increases disk pressure.'
                ),
                priority='Critical' if fs_risk_count >= 5 else 'Warning',
                source='storage_filesystem',
                source_label='Filesystem Storage',
                resource='storage',
                action_type='storage_review',
                href='/analytics/storage?tab=filesystem',
            )
        )

    pvc_summary = persistent_storage.get('pvc', {})

    if not isinstance(pvc_summary, dict):
        pvc_summary = {}

    pvc_used_percent = get_numeric_value(pvc_summary.get('used_percent', 0))
    pvc_free_percent = get_numeric_value(pvc_summary.get('free_percent', 0))

    if pvc_used_percent >= 90 or pvc_free_percent <= 10:
        priority = 'Critical'
    elif pvc_used_percent >= 75 or pvc_free_percent <= 25:
        priority = 'Warning'
    else:
        priority = ''

    if priority:
        recommendations.append(
            build_recommendation(
                title='Review PVC Capacity Utilization',
                description=(
                    f'PVC used capacity is {pvc_used_percent:.2f}% with {pvc_free_percent:.2f}% free. '
                    'Check namespace ownership, storage class expansion policy, and application growth before the volume reaches exhaustion.'
                ),
                priority=priority,
                source='storage_pvc',
                source_label='Persistent Volume Claim',
                resource='storage',
                action_type='storage_review',
                href='/analytics/storage?tab=pvc',
            )
        )

    pvc_risk_count = _count_rows_by_risk_label(
        pvc_rows,
        {'warning', 'watch', 'high', 'critical'},
    )

    if pvc_risk_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review PVC Risk Items',
                description=(
                    f'{pvc_risk_count} PVC risk item(s) require attention. '
                    'Check PVC status, used capacity, namespace ownership, and storage expansion policy before increasing workload demand.'
                ),
                priority='Critical' if pvc_risk_count >= 5 else 'Warning',
                source='storage_pvc',
                source_label='Persistent Volume Claim',
                resource='storage',
                action_type='storage_review',
                href='/analytics/storage?tab=pvc',
            )
        )

    pv_risk_count = _count_rows_by_risk_label(
        pv_rows,
        {'watch', 'critical', 'unknown'},
    )

    if pv_risk_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review PV Lifecycle Risk Items',
                description=(
                    f'{pv_risk_count} PV risk item(s) were detected. '
                    'Review Available, Released, Failed, or Unknown PV states, reclaim policy, and claim binding before cleanup or reuse.'
                ),
                priority='Critical' if _has_row_with_risk_label(pv_rows, {'critical'}) else 'Warning',
                source='storage_pv',
                source_label='Persistent Volume',
                resource='storage',
                action_type='storage_review',
                href='/analytics/storage?tab=pv',
            )
        )

    recommendations = deduplicate_recommendations(recommendations)

    if recommendations:
        return recommendations

    return [
        build_recommendation(
            title='Continue Regular Storage Monitoring',
            description=(
                'No actionable storage risk was detected from filesystem, PV, or PVC signals. '
                'Continue tracking filesystem usage, PVC growth, PV lifecycle state, and namespace storage demand.'
            ),
            priority='Normal',
            source='storage_baseline',
            source_label='Storage Baseline',
            resource='storage',
            action_type='storage_review',
            href='/analytics/storage?tab=capacity',
            is_actionable=False,
        ),
        build_recommendation(
            title='Validate Storage Classes and Reclaim Policies Periodically',
            description=(
                'Review storage class expansion capability and PV reclaim policies for critical workloads before capacity incidents occur.'
            ),
            priority='Info',
            source='storage_practice',
            source_label='Storage Operating Practice',
            resource='storage',
            action_type='storage_review',
            href='/analytics/storage?tab=capacity',
            is_actionable=False,
        ),
    ]


def build_workload_actionable_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    tenant_quota_rows = _as_list(
        payload.get('tenant_quota_rows') or (payload.get('tenant_quota_summary') or {}).get('rows', [])
        if isinstance(payload.get('tenant_quota_summary'), dict)
        else payload.get('tenant_quota_rows', [])
    )

    workload_mapping_rows = _as_list(
        payload.get('workload_mapping_rows') or (payload.get('workload_mapping_payload') or {}).get('rows', [])
        if isinstance(payload.get('workload_mapping_payload'), dict)
        else payload.get('workload_mapping_rows', [])
    )

    governance_findings = _as_list(payload.get('governance_findings', []))

    missing_quota_count = 0
    partial_quota_count = 0
    quota_near_limit_count = 0
    quota_critical_count = 0
    quota_efficiency_risk_count = 0

    for row in tenant_quota_rows:
        if not isinstance(row, dict):
            continue

        quota_status = get_status_label(row.get('quota_status', 'Unknown'))
        quota_usage_percent = get_numeric_value(row.get('quota_usage_percent', 0))
        actual_usage_percent = get_numeric_value(row.get('actual_usage_percent', 0))
        risk_label = get_status_label(row.get('risk', 'Unknown')).lower()

        if quota_status == 'Missing':
            missing_quota_count += 1
        elif quota_status == 'Partial':
            partial_quota_count += 1

        if quota_usage_percent >= 90 or risk_label == 'critical':
            quota_critical_count += 1
        elif quota_usage_percent >= 75 or risk_label in {'high', 'medium'}:
            quota_near_limit_count += 1

        if quota_usage_percent >= 75 and actual_usage_percent < 40:
            quota_efficiency_risk_count += 1

    if missing_quota_count > 0:
        recommendations.append(
            build_recommendation(
                title='Create Missing Namespace ResourceQuota',
                description=(
                    f'{missing_quota_count} namespace(s) have no ResourceQuota. '
                    'Define CPU, memory, and pod quota boundaries before allowing additional workload growth.'
                ),
                priority='Critical',
                source='workload_quota',
                source_label='Tenant Quota',
                resource='namespace',
                action_type='quota_review',
                href='/analytics/workload',
                icon='shield-alert',
            )
        )

    if partial_quota_count > 0:
        recommendations.append(
            build_recommendation(
                title='Complete Partial ResourceQuota Definitions',
                description=(
                    f'{partial_quota_count} namespace(s) have partial ResourceQuota coverage. '
                    'Add missing requests.cpu, limits.cpu, requests.memory, limits.memory, or pods quota keys.'
                ),
                priority='Warning',
                source='workload_quota',
                source_label='Tenant Quota',
                resource='namespace',
                action_type='quota_review',
                href='/analytics/workload',
                icon='shield-check',
            )
        )

    if quota_critical_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review Namespaces at Critical Quota Usage',
                description=(
                    f'{quota_critical_count} namespace(s) are at critical quota pressure. '
                    'Review allocation, actual usage, and ownership before increasing quota or scheduling new workloads.'
                ),
                priority='Critical',
                source='workload_quota',
                source_label='Tenant Quota',
                resource='namespace',
                action_type='quota_review',
                href='/analytics/workload',
                icon='triangle-alert',
            )
        )
    elif quota_near_limit_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review Namespaces Near Quota Limit',
                description=(
                    f'{quota_near_limit_count} namespace(s) are approaching quota limits. '
                    'Validate whether high allocation is expected and coordinate quota changes with application owners.'
                ),
                priority='Warning',
                source='workload_quota',
                source_label='Tenant Quota',
                resource='namespace',
                action_type='quota_review',
                href='/analytics/workload',
                icon='gauge',
            )
        )

    if quota_efficiency_risk_count > 0:
        recommendations.append(
            build_recommendation(
                title='Right-Size Quota Allocation Before Expansion',
                description=(
                    f'{quota_efficiency_risk_count} namespace(s) show high quota allocation with low actual usage. '
                    'Right-size workload requests and limits before increasing namespace quota.'
                ),
                priority='Warning',
                source='workload_rightsizing',
                source_label='Workload Right-Sizing',
                resource='namespace',
                action_type='right_size_requests',
                href='/analytics/workload',
                icon='scale',
            )
        )

    best_effort_count = 0
    missing_request_count = 0
    missing_limit_count = 0
    high_risk_count = 0
    medium_risk_count = 0
    over_requested_count = 0
    under_requested_count = 0

    for row in workload_mapping_rows:
        if not isinstance(row, dict):
            continue

        resource_status = get_status_label(row.get('resource_status', 'Unknown'))
        qos_label = get_status_label(row.get('qos', 'Unknown'))
        risk_label = get_status_label(row.get('risk', 'Unknown'))
        recommendation = str(row.get('recommendation', '') or '').lower()

        if qos_label == 'BestEffort' or resource_status == 'BestEffort':
            best_effort_count += 1

        if resource_status in {'Missing Request', 'BestEffort'}:
            missing_request_count += 1

        if resource_status in {'Missing Limit', 'BestEffort'}:
            missing_limit_count += 1

        if risk_label in {'High', 'Critical'}:
            high_risk_count += 1
        elif risk_label == 'Medium':
            medium_risk_count += 1

        if 'reduce' in recommendation:
            over_requested_count += 1

        if 'increase' in recommendation:
            under_requested_count += 1

    if best_effort_count > 0:
        recommendations.append(
            build_recommendation(
                title='Remove BestEffort Workload Risk',
                description=(
                    f'{best_effort_count} BestEffort workload(s) were detected. '
                    'Set CPU and memory requests to improve scheduling reliability and reduce noisy-neighbor risk.'
                ),
                priority='Critical',
                source='workload_governance',
                source_label='Workload Governance',
                resource='workload',
                action_type='workload_governance',
                href='/analytics/workload',
                icon='shield-alert',
            )
        )

    if missing_request_count > 0:
        recommendations.append(
            build_recommendation(
                title='Set Missing Workload Resource Requests',
                description=(
                    f'{missing_request_count} workload(s) are missing CPU or memory requests. '
                    'Define requests so scheduling, quota usage, and capacity planning reflect runtime demand.'
                ),
                priority='Warning',
                source='workload_resource_mapping',
                source_label='Workload Resource Mapping',
                resource='workload',
                action_type='workload_governance',
                href='/analytics/workload',
                icon='settings-2',
            )
        )

    if missing_limit_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review Missing Workload Limits',
                description=(
                    f'{missing_limit_count} workload(s) are missing CPU or memory limits. '
                    'Apply limit policy according to workload criticality and tenant governance requirements.'
                ),
                priority='Warning',
                source='workload_resource_mapping',
                source_label='Workload Resource Mapping',
                resource='workload',
                action_type='workload_governance',
                href='/analytics/workload',
                icon='sliders-horizontal',
            )
        )

    if under_requested_count > 0:
        recommendations.append(
            build_recommendation(
                title='Increase Resources for Under-Provisioned Workloads',
                description=(
                    f'{under_requested_count} workload(s) may need higher CPU or memory requests. '
                    'Validate recent peak usage, throttling, OOM, and application SLO impact before changing values.'
                ),
                priority='Critical' if high_risk_count > 0 else 'Warning',
                source='workload_rightsizing',
                source_label='Workload Right-Sizing',
                resource='workload',
                action_type='right_size_requests',
                href='/analytics/workload',
                icon='trending-up',
            )
        )

    if over_requested_count > 0:
        recommendations.append(
            build_recommendation(
                title='Right-Size Over-Requested Workloads',
                description=(
                    f'{over_requested_count} workload(s) appear over-requested. '
                    'Compare requests against average and peak usage before increasing quota or cluster capacity.'
                ),
                priority='Warning',
                source='workload_rightsizing',
                source_label='Workload Right-Sizing',
                resource='workload',
                action_type='right_size_requests',
                href='/analytics/workload',
                icon='scale',
            )
        )

    if high_risk_count > 0 and under_requested_count == 0 and best_effort_count == 0:
        recommendations.append(
            build_recommendation(
                title='Review High-Risk Workload Mappings',
                description=(
                    f'{high_risk_count} workload mapping row(s) are high risk. '
                    'Review resource status, QoS, efficiency, recommendation text, and workload ownership.'
                ),
                priority='Critical',
                source='workload_resource_mapping',
                source_label='Workload Resource Mapping',
                resource='workload',
                action_type='workload_governance',
                href='/analytics/workload',
                icon='circle-alert',
            )
        )
    elif medium_risk_count > 0:
        recommendations.append(
            build_recommendation(
                title='Review Medium-Risk Workload Mappings',
                description=(
                    f'{medium_risk_count} workload mapping row(s) have medium risk. '
                    'Prioritize repeated patterns across namespaces and application owners.'
                ),
                priority='Warning',
                source='workload_resource_mapping',
                source_label='Workload Resource Mapping',
                resource='workload',
                action_type='workload_governance',
                href='/analytics/workload',
                icon='activity',
            )
        )

    for finding in governance_findings:
        if not isinstance(finding, dict):
            continue

        severity = normalize_priority(finding.get('severity', 'Info'), default='Info')
        if not is_actionable_priority(severity):
            continue

        recommendations.append(
            build_recommendation(
                title=str(finding.get('label') or 'Review workload governance finding'),
                description=(
                    'Review the related namespace, workload, quota, request, or limit policy. '
                    f'Finding filter/context: {finding.get("filter", "-") or "-"}'
                ),
                priority=severity,
                source='workload_governance',
                source_label='Workload Governance',
                resource='workload',
                action_type='workload_governance',
                href='/analytics/workload',
                icon=str(finding.get('icon') or 'shield-alert'),
            )
        )

    recommendations = deduplicate_recommendations(recommendations)

    if recommendations:
        return recommendations

    return [
        build_recommendation(
            title='Continue Workload Governance Monitoring',
            description=(
                'No actionable workload governance or right-sizing risk was detected. '
                'Continue tracking ResourceQuota coverage, requests, limits, QoS class, and efficiency drift.'
            ),
            priority='Normal',
            source='workload_baseline',
            source_label='Workload Baseline',
            resource='workload',
            action_type='workload_governance',
            href='/analytics/workload',
            icon='check-circle-2',
            is_actionable=False,
        ),
        build_recommendation(
            title='Review Workload Requests and Limits Periodically',
            description=(
                'Even when workload posture is healthy, review requests and limits after major deployments, scaling events, or tenant quota changes.'
            ),
            priority='Info',
            source='workload_practice',
            source_label='Workload Operating Practice',
            resource='workload',
            action_type='workload_governance',
            href='/analytics/workload',
            icon='list-checks',
            is_actionable=False,
        ),
    ]


FORECAST_WARNING_THRESHOLD = 75.0
FORECAST_CRITICAL_THRESHOLD = 90.0


def build_forecast_actionable_recommendations(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    items = _as_list(payload.get('items', []))
    summary = payload.get('summary', {})

    if not isinstance(summary, dict):
        summary = {}

    forecast_horizon = str(
        payload.get('forecast_horizon') or payload.get('selected_forecast_horizon') or 'forecast window'
    )

    for item in items:
        if not isinstance(item, dict):
            continue

        resource_key = str(item.get('key') or '').strip().lower()
        resource_label = str(item.get('label') or resource_key.upper() or 'Resource')
        projected_percent = get_numeric_value(item.get('projected_percent', 0))
        current_percent = get_numeric_value(item.get('current_percent', 0))
        growth_per_week = get_numeric_value(item.get('growth_per_week', 0))
        confidence = str(item.get('confidence') or 'Unknown')
        confidence_reason = str(item.get('confidence_reason') or '-')
        warning_eta = item.get('warning_eta', {})
        critical_eta = item.get('critical_eta', {})

        if not isinstance(warning_eta, dict):
            warning_eta = {}

        if not isinstance(critical_eta, dict):
            critical_eta = {}

        critical_eta_label = str(critical_eta.get('label') or 'Not projected')
        warning_eta_label = str(warning_eta.get('label') or 'Not projected')

        if projected_percent >= FORECAST_CRITICAL_THRESHOLD:
            recommendations.append(
                build_recommendation(
                    title=f'Review projected {resource_label.lower()} critical threshold',
                    description=(
                        f'{resource_label} is projected to reach {projected_percent:.2f}% within {forecast_horizon}. '
                        f'Current usage is {current_percent:.2f}%. Critical ETA: {critical_eta_label}. '
                        'Validate planned deployments, growth assumptions, and capacity expansion options.'
                    ),
                    priority='Critical',
                    source='forecast_projection',
                    source_label='Forecast Projection',
                    resource=resource_key,
                    action_type='forecast_review',
                    href='/analytics/forecast',
                    icon='flame',
                )
            )
            continue

        if projected_percent >= FORECAST_WARNING_THRESHOLD:
            recommendations.append(
                build_recommendation(
                    title=f'Review projected {resource_label.lower()} warning threshold',
                    description=(
                        f'{resource_label} is projected to reach {projected_percent:.2f}% within {forecast_horizon}. '
                        f'Current usage is {current_percent:.2f}%. Warning ETA: {warning_eta_label}. '
                        'Review workload growth, requests, limits, autoscaling, and capacity headroom.'
                    ),
                    priority='Warning',
                    source='forecast_projection',
                    source_label='Forecast Projection',
                    resource=resource_key,
                    action_type='forecast_review',
                    href='/analytics/forecast',
                    icon='triangle-alert',
                )
            )

        if growth_per_week > 0 and projected_percent >= 60:
            recommendations.append(
                build_recommendation(
                    title=f'Validate {resource_label.lower()} growth trend',
                    description=(
                        f'{resource_label} has positive forecast growth and is projected to reach {projected_percent:.2f}%. '
                        'Confirm whether the trend is caused by expected workload growth, recent deployments, or abnormal usage drift.'
                    ),
                    priority='Warning' if projected_percent >= FORECAST_WARNING_THRESHOLD else 'Info',
                    source='forecast_growth',
                    source_label='Forecast Growth Trend',
                    resource=resource_key,
                    action_type='forecast_review',
                    href='/analytics/forecast',
                    icon='trending-up',
                    is_actionable=projected_percent >= FORECAST_WARNING_THRESHOLD,
                )
            )

        if confidence.lower() == 'low' and projected_percent >= FORECAST_WARNING_THRESHOLD:
            recommendations.append(
                build_recommendation(
                    title=f'Validate low-confidence {resource_label.lower()} forecast',
                    description=(
                        f'{resource_label} forecast confidence is Low. Reason: {confidence_reason}. '
                        'Validate with a longer history window and compare with recent incidents, deployments, or traffic changes before making capacity decisions.'
                    ),
                    priority='Warning',
                    source='forecast_confidence',
                    source_label='Forecast Confidence',
                    resource=resource_key,
                    action_type='forecast_review',
                    href='/analytics/forecast',
                    icon='sigma',
                )
            )

    nearest_critical = summary.get('nearest_critical', {})
    nearest_warning = summary.get('nearest_warning', {})

    if not isinstance(nearest_critical, dict):
        nearest_critical = {}

    if not isinstance(nearest_warning, dict):
        nearest_warning = {}

    critical_days = nearest_critical.get('days')
    warning_days = nearest_warning.get('days')

    if isinstance(critical_days, int | float) and critical_days <= 30:
        recommendations.append(
            build_recommendation(
                title='Prioritize Nearest Critical Forecast Breach',
                description=(
                    f'{nearest_critical.get("resource", "A resource")} is projected to reach critical threshold in '
                    f'{nearest_critical.get("label", f"{int(critical_days)} days")}. '
                    'Create a capacity action plan before the projected critical date.'
                ),
                priority='Critical',
                source='forecast_eta',
                source_label='Forecast Threshold ETA',
                resource='forecast',
                action_type='forecast_review',
                href='/analytics/forecast',
                icon='calendar-clock',
            )
        )
    elif isinstance(warning_days, int | float) and warning_days <= 30:
        recommendations.append(
            build_recommendation(
                title='Review Nearest Forecast Warning Breach',
                description=(
                    f'{nearest_warning.get("resource", "A resource")} is projected to reach warning threshold in '
                    f'{nearest_warning.get("label", f"{int(warning_days)} days")}. '
                    'Review whether this trend is expected and prepare quota, node, or workload adjustments.'
                ),
                priority='Warning',
                source='forecast_eta',
                source_label='Forecast Threshold ETA',
                resource='forecast',
                action_type='forecast_review',
                href='/analytics/forecast',
                icon='calendar-clock',
            )
        )

    recommendations = deduplicate_recommendations(recommendations)

    if recommendations:
        return recommendations

    return [
        build_recommendation(
            title='Continue Forecast Monitoring',
            description=(
                'No actionable forecast risk was detected from projected resource growth. '
                'Continue tracking forecast trend after major deployments, scaling events, and capacity changes.'
            ),
            priority='Normal',
            source='forecast_baseline',
            source_label='Forecast Baseline',
            resource='forecast',
            action_type='forecast_review',
            href='/analytics/forecast',
            icon='check-circle-2',
            is_actionable=False,
        ),
        build_recommendation(
            title='Validate Forecast Assumptions Periodically',
            description=(
                'Use forecast output as an early planning signal. Re-check with longer history windows when historical data is noisy or limited.'
            ),
            priority='Info',
            source='forecast_practice',
            source_label='Forecast Practice',
            resource='forecast',
            action_type='forecast_review',
            href='/analytics/forecast',
            icon='sigma',
            is_actionable=False,
        ),
    ]


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    return []


def _get_row_risk_label(row: Any) -> str:
    if not isinstance(row, dict):
        return ''

    risk = row.get('risk', {})

    if isinstance(risk, dict):
        return str(risk.get('label', '') or '').strip().lower()

    return str(risk or '').strip().lower()


def _count_rows_by_risk_label(
    rows: list[Any],
    risk_labels: set[str],
) -> int:
    allowed = {label.lower() for label in risk_labels}

    return sum(1 for row in rows if _get_row_risk_label(row) in allowed)


def _has_row_with_risk_label(
    rows: list[Any],
    risk_labels: set[str],
) -> bool:
    allowed = {label.lower() for label in risk_labels}

    return any(_get_row_risk_label(row) in allowed for row in rows)


def build_top_consumers_actionable_recommendations(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    consumer_payload = payload.get('consumer_payload') if isinstance(payload.get('consumer_payload'), dict) else payload
    if not isinstance(consumer_payload, dict):
        consumer_payload = {}

    rows = consumer_payload.get('all_rows')
    if not isinstance(rows, list):
        rows = consumer_payload.get('rows', [])
    if not isinstance(rows, list):
        rows = []

    missing_requests = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get('resource_type', '')).lower() in {'cpu', 'memory'}
        and get_numeric_value(row.get('request', 0)) <= 0
    ]
    high_usage = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get('resource_type', '')).lower() in {'cpu', 'memory'}
        and get_numeric_value(row.get('usage_percent', 0)) >= 75
    ]
    critical_usage = [
        row
        for row in high_usage
        if isinstance(row, dict)
        and (
            get_status_label(row.get('risk', '')).lower() == 'critical'
            or get_numeric_value(row.get('usage_percent', 0)) >= 90
        )
    ]
    high_pvc = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get('resource_type', '')).lower() == 'pvc'
        and get_numeric_value(row.get('usage_percent', 0)) >= 80
    ]
    critical_pvc = [
        row
        for row in high_pvc
        if isinstance(row, dict)
        and (
            get_status_label(row.get('risk', '')).lower() == 'critical'
            or get_numeric_value(row.get('usage_percent', 0)) >= 90
        )
    ]

    dominant_namespaces = get_top_consumer_dominant_namespaces(rows)

    if missing_requests:
        recommendations.append(
            build_recommendation(
                title='Add Missing CPU and Memory Requests',
                description=(
                    f'{len(missing_requests)} top consumer row(s) are missing CPU or memory requests. '
                    'Set requests so Kubernetes can schedule these workloads predictably and capacity reports are meaningful.'
                ),
                priority='Warning',
                source='top_consumers_missing_requests',
                resource='cpu',
                action_type='missing_requests',
                href='/analytics/top-consumers?focus=missing_requests',
                icon='activity',
            )
        )

    if high_usage:
        priority = 'Critical' if critical_usage else 'Warning'
        recommendations.append(
            build_recommendation(
                title='Review High CPU and Memory Consumers',
                description=(
                    f'{len(high_usage)} CPU or memory consumer row(s) are above the warning threshold. '
                    'Validate whether the usage is expected, then tune requests/limits or scale the workload.'
                ),
                priority=priority,
                source='top_consumers_high_usage',
                resource='cpu',
                action_type='high_usage',
                href='/analytics/top-consumers?focus=high_usage',
                icon='flame',
            )
        )

    if dominant_namespaces:
        namespace_text = ', '.join(dominant_namespaces[:3])
        recommendations.append(
            build_recommendation(
                title='Investigate Dominant Resource Namespaces',
                description=(
                    f'{len(dominant_namespaces)} namespace(s) repeatedly appear in high-consumer rows: {namespace_text}. '
                    'Review tenant ownership, quota coverage, and workload growth before expanding shared capacity.'
                ),
                priority='Warning',
                source='top_consumers_dominant_namespaces',
                resource='namespace',
                action_type='dominant_namespaces',
                href='/analytics/top-consumers?focus=dominant_namespaces',
                icon='network',
            )
        )

    if high_pvc:
        priority = 'Critical' if critical_pvc else 'Warning'
        recommendations.append(
            build_recommendation(
                title='Clean Up or Expand High PVC Usage',
                description=(
                    f'{len(high_pvc)} PVC consumer row(s) are using at least 80% of capacity. '
                    'Review cleanup, retention, storage expansion, and owning namespace before usage becomes disruptive.'
                ),
                priority=priority,
                source='top_consumers_high_pvc',
                resource='storage',
                action_type='high_pvc',
                href='/analytics/top-consumers?resource=pvc&focus=high_pvc',
                icon='database',
            )
        )

    if not recommendations:
        recommendations.extend(
            [
                build_recommendation(
                    title='No Critical Consumer Hotspot Detected',
                    description=(
                        'Top consumer rows are currently below actionable hotspot thresholds. '
                        'Continue reviewing this page during incidents, deployments, and capacity reviews.'
                    ),
                    priority='Normal',
                    source='top_consumers_baseline',
                    resource='consumer',
                    action_type='monitoring',
                    icon='check-circle-2',
                    is_actionable=False,
                ),
                build_recommendation(
                    title='Review Top Consumers Periodically',
                    description=(
                        'Use Top Consumers as the first drilldown when utilization, capacity, or forecast pages show pressure.'
                    ),
                    priority='Info',
                    source='top_consumers_practice',
                    resource='consumer',
                    action_type='review',
                    icon='scan-search',
                    is_actionable=False,
                ),
            ]
        )

    return deduplicate_recommendations(recommendations)


def get_top_consumer_dominant_namespaces(rows: list[Any]) -> list[str]:
    namespace_scores: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        namespace = str(row.get('namespace', '') or '')
        if not namespace:
            continue

        usage_percent = get_numeric_value(row.get('usage_percent', 0))
        risk_label = get_status_label(row.get('risk', '')).lower()

        if usage_percent < 75 and risk_label not in {'warning', 'critical'}:
            continue

        namespace_scores[namespace] = namespace_scores.get(namespace, 0) + 1

    return [
        namespace
        for namespace, _score in sorted(
            namespace_scores.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )[:3]
    ]


def build_alerts_actionable_recommendations(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    if not isinstance(payload, dict):
        payload = {}

    alerts = payload.get('all_alerts')
    if not isinstance(alerts, list):
        alerts = payload.get('alerts', [])
    if not isinstance(alerts, list):
        alerts = []

    anomalies = payload.get('all_anomalies')
    if not isinstance(anomalies, list):
        anomalies = payload.get('anomalies', [])
    if not isinstance(anomalies, list):
        anomalies = []

    source_status = payload.get('source_status')
    if not isinstance(source_status, dict):
        source_status = {}

    signal_overview = payload.get('selected_cluster_signal_overview')
    if not isinstance(signal_overview, dict):
        signal_overview = {}

    active_alerts = [
        item
        for item in alerts
        if isinstance(item, dict) and str(item.get('status', '')).lower() in {'active', 'firing', 'pending'}
    ]
    critical_alerts = [item for item in active_alerts if str(item.get('severity', '')).lower() == 'critical']
    warning_alerts = [item for item in active_alerts if str(item.get('severity', '')).lower() == 'warning']
    critical_anomalies = [
        item for item in anomalies if isinstance(item, dict) and str(item.get('severity', '')).lower() == 'critical'
    ]

    if not bool(source_status.get('connected', False)):
        recommendations.append(
            build_recommendation(
                title='Restore Alert Source Connectivity',
                description=(
                    'The selected alert source is not connected. Verify Prometheus and Alertmanager endpoint, '
                    'credentials, network access, and fallback mode before relying on alert analysis.'
                ),
                priority='Warning',
                source='alerts_source',
                resource='alerts',
                action_type='source_health',
                href='/analytics/alerts-anomalies',
                icon='circle-alert',
            )
        )

    if critical_alerts:
        first_alert = critical_alerts[0]
        alert_name = str(first_alert.get('name', 'critical alert') or 'critical alert')
        recommendations.append(
            build_recommendation(
                title='Prioritize Active Critical Alerts',
                description=(
                    f'{len(critical_alerts)} active critical alert(s) detected. Start with {alert_name}, '
                    'review affected namespace/target, confirm blast radius, then follow the runbook or escalation path.'
                ),
                priority='Critical',
                source='alerts_critical',
                resource='alerts',
                action_type='critical_alert_review',
                href='/analytics/alerts-anomalies-anomalies?severity=critical',
                icon='circle-alert',
            )
        )

    if warning_alerts:
        recommendations.append(
            build_recommendation(
                title='Review Warning Alerts Before Escalation',
                description=(
                    f'{len(warning_alerts)} active warning alert(s) detected. Validate whether these signals are '
                    'expected workload behavior or early degradation that needs remediation.'
                ),
                priority='Warning',
                source='alerts_warning',
                resource='alerts',
                action_type='warning_alert_review',
                href='/analytics/alerts-anomalies-anomalies?severity=warning',
                icon='alert-triangle',
            )
        )

    if anomalies:
        priority = 'Critical' if critical_anomalies else 'Warning'
        restart_count = sum(
            1
            for item in anomalies
            if isinstance(item, dict) and str(item.get('name', '')).lower() == 'pod restart spike'
        )
        not_ready_count = sum(
            1 for item in anomalies if isinstance(item, dict) and str(item.get('name', '')).lower() == 'pod not ready'
        )
        recommendations.append(
            build_recommendation(
                title='Investigate Anomaly Candidates',
                description=(
                    f'{len(anomalies)} anomaly candidate(s) detected from Prometheus signals '
                    f'({restart_count} restart spike, {not_ready_count} not-ready). Review pod events, logs, probes, '
                    'recent rollouts, and resource pressure for affected workloads.'
                ),
                priority=priority,
                source='alerts_anomaly',
                resource='pod',
                action_type='anomaly_review',
                href='/analytics/alerts-anomalies',
                icon='radar',
            )
        )

    affected_resources = get_alerts_affected_resource_count(
        alerts=active_alerts,
        anomalies=anomalies,
    )
    if affected_resources >= 3:
        recommendations.append(
            build_recommendation(
                title='Correlate Affected Namespaces and Targets',
                description=(
                    f'{affected_resources} affected namespace/target pair(s) have active alert or anomaly signals. '
                    'Group the investigation by namespace, target, and owner before changing workload or cluster capacity.'
                ),
                priority='Warning',
                source='alerts_affected_resources',
                resource='namespace',
                action_type='affected_resource_review',
                href='/analytics/alerts-anomalies',
                icon='git-branch',
            )
        )

    if not recommendations:
        priority = _as_dict(signal_overview.get('priority'))
        recommendations.extend(
            [
                build_recommendation(
                    title='No Active Alert or Anomaly Action Required',
                    description=str(
                        priority.get(
                            'description',
                            'No active alert or anomaly signal is currently detected for the selected scope.',
                        )
                    ),
                    priority='Normal',
                    source='alerts_baseline',
                    resource='alerts',
                    action_type='monitoring',
                    icon='shield-check',
                    is_actionable=False,
                ),
                build_recommendation(
                    title='Keep Alert Response Resources Current',
                    description=(
                        'Validate Alertmanager routing, runbook links, contact points, and ownership metadata so alerts '
                        'remain actionable during incidents.'
                    ),
                    priority='Info',
                    source='alerts_practice',
                    resource='alerts',
                    action_type='response_readiness',
                    icon='book-open-check',
                    is_actionable=False,
                ),
            ]
        )

    return deduplicate_recommendations(recommendations)


def get_alerts_affected_resource_count(
    *,
    alerts: list[Any],
    anomalies: list[Any],
) -> int:
    resource_keys: set[str] = set()

    for item in [*alerts, *anomalies]:
        if not isinstance(item, dict):
            continue

        namespace = str(item.get('namespace', '-') or '-')
        target = str(item.get('target', '-') or '-')
        resource_keys.add(f'{namespace}/{target}')

    return len(resource_keys)


# ---------------------------------------------------------------------------
# CENTRALIZED ANALYTICS OVERVIEW RECOMMENDATION HELPERS
# ---------------------------------------------------------------------------
FloatLike = str | bytes | SupportsFloat | SupportsIndex


SEVERITY_TONES = {
    'critical': 'red',
    'high': 'red',
    'warning': 'amber',
    'medium': 'amber',
    'low': 'blue',
    'normal': 'green',
    'info': 'gray',
}

PRIORITY_TO_SEVERITY = {
    'critical': 'critical',
    'warning': 'medium',
    'normal': 'normal',
    'info': 'info',
}

SOURCE_ROUTES = {
    'capacity': ('/analytics/capacity', 'Open capacity analysis', 'bar-chart-3'),
    'capacity analysis': ('/analytics/capacity', 'Open capacity analysis', 'bar-chart-3'),
    'capacity risk summary': ('/analytics/capacity', 'Open capacity analysis', 'bar-chart-3'),
    'capacity headroom threshold': ('/analytics/capacity', 'Open capacity analysis', 'bar-chart-3'),
    'capacity governance finding': ('/analytics/capacity', 'Open capacity analysis', 'bar-chart-3'),
    'utilization': ('/analytics/utilization', 'Open utilization', 'activity'),
    'utilization risk assessment': ('/analytics/utilization', 'Open utilization', 'activity'),
    'top cpu consumer': ('/analytics/top-consumers', 'Open top consumers', 'list-ordered'),
    'top memory consumer': ('/analytics/top-consumers', 'Open top consumers', 'list-ordered'),
    'storage': ('/analytics/storage', 'Open storage analysis', 'database'),
    'workload': ('/analytics/workload', 'Open workload analysis', 'boxes'),
    'forecast': ('/analytics/forecast', 'Open forecast', 'line-chart'),
    'top_consumers': ('/analytics/top-consumers', 'Open top consumers', 'list-ordered'),
    'top consumers': ('/analytics/top-consumers', 'Open top consumers', 'list-ordered'),
    'alerts': ('/analytics/alerts-anomalies', 'Open alerts', 'bell'),
    'alerts & anomalies': ('/analytics/alerts-anomalies', 'Open alerts', 'bell'),
    'alerts_and_anomalies': ('/analytics/alerts-anomalies', 'Open alerts', 'bell'),
}


def _recommendation(
    *,
    title: str,
    description: str,
    severity: str,
    icon: str,
    href: str,
    priority: int,
    action_label: str,
    source: str = 'overview',
    source_label: str = 'Overview',
    is_actionable: bool = True,
) -> dict[str, Any]:
    normalized_severity = severity.lower().strip() or 'info'
    severity_tone = SEVERITY_TONES.get(
        normalized_severity,
        'gray',
    )

    return {
        'title': title,
        'description': description,
        'severity': normalized_severity,
        'severity_tone': severity_tone,
        'icon': icon,
        'href': href,
        'priority': priority,
        'rank': priority,
        'action_label': action_label,
        'source': source,
        'source_label': source_label,
        'is_actionable': is_actionable,
    }


def build_operational_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    actionable_recommendations = _build_from_actionable_recommendations(
        payload,
    )

    recommendations.extend(
        actionable_recommendations,
    )

    resource_snapshot = _as_dict(
        payload.get(
            'resource_snapshot',
        )
    )
    storage_snapshot = _as_dict(
        payload.get(
            'storage_snapshot',
        )
    )
    workload_snapshot = _as_dict(
        payload.get(
            'workload_snapshot',
        )
    )
    forecast_snapshot = _as_dict(
        payload.get(
            'forecast_snapshot',
        )
    )
    alerts_snapshot = _as_dict(
        payload.get(
            'alerts_snapshot',
        )
    )
    top_consumers = _as_dict(
        payload.get(
            'top_consumers',
        )
    )

    if not actionable_recommendations:
        recommendations.extend(
            _build_alert_recommendations(
                alerts_snapshot,
            )
        )
        recommendations.extend(
            _build_resource_pressure_recommendations(
                resource_snapshot,
            )
        )
        recommendations.extend(
            _build_storage_recommendations(
                storage_snapshot,
            )
        )
        recommendations.extend(
            _build_workload_recommendations(
                workload_snapshot,
            )
        )
        recommendations.extend(
            _build_forecast_recommendations(
                forecast_snapshot,
            )
        )
        recommendations.extend(
            _build_top_consumer_recommendations(
                top_consumers,
                resource_snapshot,
            )
        )

    recommendations = _deduplicate_recommendations(
        recommendations,
    )

    if not recommendations:
        recommendations.append(
            _recommendation(
                title='No Urgent Operational Recommendation',
                description=(
                    'No immediate risk was detected from the current overview snapshot. '
                    'Continue monitoring utilization, capacity, storage, workload settings, forecast, and alerts.'
                ),
                severity='info',
                icon='circle-check',
                href='/analytics',
                priority=99,
                action_label='Stay on overview',
                source='baseline',
                source_label='Healthy state',
                is_actionable=False,
            )
        )

    return sorted(
        recommendations,
        key=lambda recommendation: int(
            recommendation.get(
                'priority',
                99,
            )
        ),
    )[:6]


def _build_from_actionable_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = _as_dict(
        payload.get(
            'actionable_recommendations',
        )
    )

    items = summary.get(
        'items',
        [],
    )

    if not isinstance(
        items,
        list,
    ):
        items = []

    recommendations: list[dict[str, Any]] = []

    for index, item in enumerate(
        items,
        start=1,
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        priority_label = str(
            item.get(
                'priority',
                'Info',
            )
            or 'Info'
        )
        severity = PRIORITY_TO_SEVERITY.get(
            priority_label.lower(),
            'info',
        )

        if severity in {
            'normal',
            'info',
        }:
            continue

        source = str(
            item.get(
                'source',
                'actionable',
            )
            or 'actionable'
        )
        source_key = source.lower()
        default_href, default_action_label, default_icon = SOURCE_ROUTES.get(
            source_key,
            ('/analytics', 'Review details', 'list-checks'),
        )
        href = str(item.get('href') or default_href)
        action_label = str(item.get('action_label') or default_action_label)
        icon = str(item.get('icon') or default_icon)
        source_label = str(item.get('source_label') or source)

        priority_rank = (
            _safe_int(
                _as_float_like(
                    item.get(
                        'rank',
                        index,
                    )
                )
            )
            or index
        )

        recommendations.append(
            _recommendation(
                title=str(
                    item.get(
                        'title',
                        'Review actionable finding',
                    )
                    or 'Review actionable finding'
                ),
                description=str(
                    item.get(
                        'description',
                        'Review the related analytics page for operational context.',
                    )
                    or 'Review the related analytics page for operational context.'
                ),
                severity=severity,
                icon=icon,
                href=href,
                priority=priority_rank,
                action_label=action_label,
                source=source_key,
                source_label=source_label,
                is_actionable=True,
            )
        )

    return recommendations


def _build_alert_recommendations(alerts_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    firing_alerts = _safe_int(_as_float_like(alerts_snapshot.get('firing_alerts')))
    pending_alerts = _safe_int(_as_float_like(alerts_snapshot.get('pending_alerts')))
    critical_alerts = _safe_int(_as_float_like(alerts_snapshot.get('critical_alerts')))
    warning_alerts = _safe_int(_as_float_like(alerts_snapshot.get('warning_alerts')))
    recent_anomalies = _safe_int(_as_float_like(alerts_snapshot.get('recent_anomalies')))
    active_alerts = firing_alerts + pending_alerts

    if critical_alerts > 0:
        recommendations.append(
            _recommendation(
                title='Prioritize Critical Alerts',
                description=(
                    f'{critical_alerts} critical alert(s) are active. Review affected namespace, '
                    'target, labels, and runbook before running optimization actions.'
                ),
                severity='critical',
                icon='circle-alert',
                href=str(alerts_snapshot.get('href') or '/analytics/alerts-anomalies'),
                priority=20,
                action_label='Open alerts',
                source='alerts',
                source_label='Alerts',
            )
        )
    elif active_alerts > 0 or warning_alerts > 0:
        recommendations.append(
            _recommendation(
                title='Investigate Active Alert Signals',
                description=(
                    f'{firing_alerts} firing, {pending_alerts} pending, and '
                    f'{warning_alerts} warning alert(s) detected. Validate service impact first.'
                ),
                severity='high' if active_alerts > 0 else 'medium',
                icon='bell',
                href=str(alerts_snapshot.get('href') or '/analytics/alerts-anomalies'),
                priority=30,
                action_label='Review alerts',
                source='alerts',
                source_label='Alerts',
            )
        )

    if recent_anomalies > 0:
        recommendations.append(
            _recommendation(
                title='Review Anomaly Candidates',
                description=(
                    f'{recent_anomalies} anomaly candidate(s) detected from restart or readiness signals. '
                    'Check recent deployments, probes, and container logs.'
                ),
                severity='medium',
                icon='activity',
                href=str(alerts_snapshot.get('href') or '/analytics/alerts-anomalies'),
                priority=35,
                action_label='Open anomalies',
                source='anomalies',
                source_label='Anomalies',
            )
        )

    return recommendations


def _build_resource_pressure_recommendations(resource_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    cpu_percent = _safe_percent(_get_nested_float(resource_snapshot, 'cpu', 'percent'))
    memory_percent = _safe_percent(_get_nested_float(resource_snapshot, 'memory', 'percent'))
    storage_percent = _safe_percent(_get_nested_float(resource_snapshot, 'storage', 'percent'))
    pod_percent = _safe_percent(_get_nested_float(resource_snapshot, 'pods', 'percent'))

    resource_pressures = {
        'CPU': cpu_percent,
        'Memory': memory_percent,
        'Storage': storage_percent,
        'Pods': pod_percent,
    }
    highest_resource = max(
        resource_pressures,
        key=lambda resource_name: resource_pressures[resource_name],
    )
    highest_percent = resource_pressures[highest_resource]

    if highest_percent < 75:
        return []

    return [
        _recommendation(
            title=f'Review {highest_resource.lower()} pressure',
            description=(
                f'{highest_resource} is the highest resource pressure at '
                f'{int(round(highest_percent))}%. Open detail analysis and validate top consumers.'
            ),
            severity='critical' if highest_percent >= 90 else 'high',
            icon=_get_resource_icon(highest_resource),
            href=_get_resource_href(highest_resource),
            priority=40,
            action_label='Open resource analysis',
            source='utilization',
            source_label='Resource pressure',
        )
    ]


def _build_storage_recommendations(storage_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    pvc_risk_count = _safe_int(_as_float_like(storage_snapshot.get('pvc_risk_count')))

    if pvc_risk_count <= 0:
        return []

    return [
        _recommendation(
            title='Investigate PVC Risk Items',
            description=(
                f'{pvc_risk_count} PVC risk item(s) require attention. Review high usage, '
                'PVC status, and storage class expansion policy.'
            ),
            severity='high' if pvc_risk_count >= 5 else 'medium',
            icon='hard-drive',
            href=str(storage_snapshot.get('href') or '/analytics/storage'),
            priority=50,
            action_label='Open storage analysis',
            source='storage',
            source_label='Storage',
        )
    ]


def _build_workload_recommendations(workload_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    missing_cpu_requests = _safe_int(_as_float_like(workload_snapshot.get('missing_cpu_requests')))
    missing_memory_requests = _safe_int(_as_float_like(workload_snapshot.get('missing_memory_requests')))
    missing_cpu_limits = _safe_int(_as_float_like(workload_snapshot.get('missing_cpu_limits')))
    missing_memory_limits = _safe_int(_as_float_like(workload_snapshot.get('missing_memory_limits')))
    over_provisioned = _safe_int(_as_float_like(workload_snapshot.get('over_provisioned')))
    under_provisioned = _safe_int(_as_float_like(workload_snapshot.get('under_provisioned')))
    missing_baseline_total = missing_cpu_requests + missing_memory_requests + missing_cpu_limits + missing_memory_limits

    if missing_baseline_total > 0:
        recommendations.append(
            _recommendation(
                title='Define Missing Workload Resource Settings',
                description=(
                    f'{missing_baseline_total} workload resource setting(s) are missing. '
                    'Define CPU/memory requests and limits to improve scheduling and quota accuracy.'
                ),
                severity='medium',
                icon='settings-2',
                href=str(workload_snapshot.get('href') or '/analytics/workload'),
                priority=60,
                action_label='Open workload analysis',
                source='workload',
                source_label='Workload',
            )
        )

    if over_provisioned > 0:
        recommendations.append(
            _recommendation(
                title='Right-Size Over-Provisioned Workloads',
                description=(
                    f'{over_provisioned} workload(s) appear over-provisioned. Compare requests '
                    'against actual usage before increasing namespace or cluster capacity.'
                ),
                severity='medium',
                icon='scale',
                href=str(workload_snapshot.get('href') or '/analytics/workload'),
                priority=70,
                action_label='Review right-sizing',
                source='workload',
                source_label='Workload',
            )
        )

    if under_provisioned > 0:
        recommendations.append(
            _recommendation(
                title='Increase Resources for Under-Provisioned Workloads',
                description=(
                    f'{under_provisioned} workload(s) may need higher request or limit values. '
                    'Validate usage trend and recent throttling or OOM symptoms.'
                ),
                severity='high',
                icon='trending-up',
                href=str(workload_snapshot.get('href') or '/analytics/workload'),
                priority=80,
                action_label='Review workload risk',
                source='workload',
                source_label='Workload',
            )
        )

    return recommendations


def _build_forecast_recommendations(forecast_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    forecast_risk_count = _safe_int(_as_float_like(forecast_snapshot.get('risk_count')))
    forecast_risk = str(forecast_snapshot.get('forecast_risk', 'Low'))
    highest_projected_resource = str(forecast_snapshot.get('highest_projected_resource', 'N/A'))
    highest_projected_percent = _safe_int(_as_float_like(forecast_snapshot.get('highest_projected_percent', 0)))

    if forecast_risk_count <= 0 and forecast_risk.lower() not in {'medium', 'high', 'critical'}:
        return []

    return [
        _recommendation(
            title='Review Forecast Capacity Risk',
            description=(
                f'{highest_projected_resource} is projected at '
                f'{highest_projected_percent}% in the forecast window. '
                'Review growth trend before the next capacity planning cycle.'
            ),
            severity='high' if forecast_risk.lower() in {'high', 'critical'} else 'medium',
            icon='line-chart',
            href=str(forecast_snapshot.get('href') or '/analytics/forecast'),
            priority=90,
            action_label='Open forecast',
            source='forecast',
            source_label='Forecast',
        )
    ]


def _build_top_consumer_recommendations(
    top_consumers: dict[str, Any],
    resource_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    if not _has_top_consumer_data(top_consumers):
        return []

    highest_percent = max(
        _safe_percent(_get_nested_float(resource_snapshot, 'cpu', 'percent')),
        _safe_percent(_get_nested_float(resource_snapshot, 'memory', 'percent')),
        _safe_percent(_get_nested_float(resource_snapshot, 'storage', 'percent')),
        _safe_percent(_get_nested_float(resource_snapshot, 'pods', 'percent')),
    )

    if highest_percent < 60:
        return []

    return [
        _recommendation(
            title='Validate Top Consumers Before Remediation',
            description=(
                'Top consumer data is available. Review CPU, memory, and storage leaders '
                'before changing requests, limits, quotas, or node capacity.'
            ),
            severity='low',
            icon='list-ordered',
            href=str(top_consumers.get('href') or '/analytics/top-consumers'),
            priority=100,
            action_label='Open top consumers',
            source='top_consumers',
            source_label='Top Consumers',
        )
    ]


def _get_resource_icon(resource: str) -> str:
    icon_map = {
        'CPU': 'cpu',
        'Memory': 'memory-stick',
        'Storage': 'database',
        'Pods': 'boxes',
    }
    return icon_map.get(resource, 'gauge')


def _get_resource_href(resource: str) -> str:
    href_map = {
        'CPU': '/analytics/utilization',
        'Memory': '/analytics/utilization',
        'Storage': '/analytics/storage',
        'Pods': '/analytics/capacity',
    }
    return href_map.get(resource, '/analytics/utilization')


def _has_top_consumer_data(top_consumers: dict[str, Any]) -> bool:
    for key in ['cpu', 'memory', 'storage']:
        value = top_consumers.get(key, [])
        if isinstance(value, list) and value:
            return True
    return False


def _deduplicate_recommendations(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduplicated: list[dict[str, Any]] = []

    for item in recommendations:
        key = (
            str(item.get('title', '')).strip().lower(),
            str(item.get('source_label', '')).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)

    return deduplicated


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _get_nested_float(source: dict[str, Any], first_key: str, second_key: str) -> FloatLike | None:
    first_value = source.get(first_key)
    if not isinstance(first_value, dict):
        return None
    return _as_float_like(first_value.get(second_key))


def _as_float_like(value: Any) -> FloatLike | None:
    if isinstance(value, int | float | str | bytes):
        return value
    return None


def _safe_percent(value: FloatLike | None) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: FloatLike | None) -> int:
    if value is None:
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
