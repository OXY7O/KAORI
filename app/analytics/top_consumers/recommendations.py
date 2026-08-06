from __future__ import annotations

from typing import Any

from app.intelligence.recommendation_engine import (
    build_recommendation,
    deduplicate_recommendations,
    get_numeric_value,
    get_status_label,
)


def _top_consumers_payload(payload: dict[str, Any]) -> dict[str, Any]:
    consumer_payload = payload.get('consumer_payload')
    return consumer_payload if isinstance(consumer_payload, dict) else payload


def _top_consumers_rows(consumer_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = consumer_payload.get('all_rows')
    if not isinstance(rows, list):
        rows = consumer_payload.get('rows', [])
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _top_consumers_recommendation_facts(
    consumer_payload: dict[str, Any],
) -> dict[str, Any]:
    rows = _top_consumers_rows(consumer_payload)
    missing_requests = [
        row
        for row in rows
        if str(row.get('resource_type', '')).lower() in {'cpu', 'memory'}
        and row.get('request_evidence_available') is True
        and get_numeric_value(row.get('request', 0)) <= 0
    ]
    high_compute_pressure = [
        row
        for row in rows
        if str(row.get('resource_type', '')).lower() in {'cpu', 'memory'}
        and row.get('pressure_percent') is not None
        and get_numeric_value(row.get('pressure_percent', 0)) >= 75
    ]
    critical_compute_pressure = [
        row
        for row in high_compute_pressure
        if get_status_label(row.get('risk', '')).lower()
        in {'critical', 'request missing'}
        or get_numeric_value(row.get('pressure_percent', 0)) >= 90
    ]
    memory_limit_review = [
        row
        for row in rows
        if str(row.get('resource_type', '')).lower() == 'memory'
        and row.get('request_evidence_available') is True
        and row.get('limit_evidence_available') is True
        and get_numeric_value(row.get('request', 0)) > 0
        and get_numeric_value(row.get('limit', 0)) <= 0
    ]
    high_pvc = [
        row
        for row in rows
        if str(row.get('resource_type', '')).lower() == 'pvc'
        and row.get('pressure_percent') is not None
        and get_numeric_value(row.get('pressure_percent', 0)) >= 80
    ]
    coverage = (
        consumer_payload.get('coverage')
        if isinstance(consumer_payload.get('coverage'), dict)
        else {}
    )
    return {
        'rows': rows,
        'missing_requests': missing_requests,
        'high_compute_pressure': high_compute_pressure,
        'critical_compute_pressure': critical_compute_pressure,
        'memory_limit_review': memory_limit_review,
        'high_pvc': high_pvc,
        'critical_pvc': [
            row
            for row in high_pvc
            if get_numeric_value(row.get('pressure_percent', 0)) >= 90
        ],
        'incomplete_resources': (
            get_numeric_value(coverage.get('partial_count', 0))
            + get_numeric_value(coverage.get('unavailable_count', 0))
        ),
        'dominant_namespaces': get_top_consumer_dominant_namespaces(rows),
    }


def _missing_request_recommendation(
    facts: dict[str, Any],
) -> dict[str, Any] | None:
    rows = facts['missing_requests']
    if not rows:
        return None
    return build_recommendation(
        title='Add Missing CPU and Memory Requests',
        description=(
            f'{len(rows)} top consumer row(s) are missing CPU or memory requests. '
            'Set requests so Kubernetes scheduling and consumer pressure analysis '
            'have a reliable boundary.'
        ),
        priority='Critical',
        source='top_consumers_missing_requests',
        resource='cpu',
        action_type='missing_requests',
        href=(
            '/analytics/top-consumers?tab=records&focus=missing_requests'
            '&priority=critical'
        ),
        icon='activity',
    )


def _compute_pressure_recommendation(
    facts: dict[str, Any],
) -> dict[str, Any] | None:
    rows = facts['high_compute_pressure']
    if not rows:
        return None
    return build_recommendation(
        title='Review High CPU and Memory Consumer Pressure',
        description=(
            f'{len(rows)} CPU or memory consumer row(s) are above the warning '
            'boundary. Review request utilization, limit utilization, '
            'contribution to scope, scaling, and ownership.'
        ),
        priority=(
            'Critical' if facts['critical_compute_pressure'] else 'Warning'
        ),
        source='top_consumers_high_usage',
        resource='cpu',
        action_type='high_usage',
        href='/analytics/top-consumers?tab=records&focus=high_usage',
        icon='flame',
    )


def _memory_limit_recommendation(
    facts: dict[str, Any],
) -> dict[str, Any] | None:
    rows = facts['memory_limit_review']
    if not rows:
        return None
    return build_recommendation(
        title='Review Missing Memory Limit Coverage',
        description=(
            f'{len(rows)} memory consumer row(s) have requests but no memory '
            'limit. Validate workload criticality and memory policy; CPU limits '
            'may remain intentionally unset.'
        ),
        priority='Warning',
        source='top_consumers_high_usage',
        resource='memory',
        action_type='memory_limit_review',
        href=(
            '/analytics/top-consumers?tab=records&resource=memory'
            '&priority=warning'
        ),
        icon='memory-stick',
    )


def _dominant_namespace_recommendation(
    facts: dict[str, Any],
) -> dict[str, Any] | None:
    namespaces = facts['dominant_namespaces']
    if not namespaces:
        return None
    namespace_text = ', '.join(namespaces[:3])
    return build_recommendation(
        title='Investigate Dominant Resource Namespaces',
        description=(
            f'{len(namespaces)} namespace(s) repeatedly contribute significant '
            f'consumer pressure: {namespace_text}. Review tenant ownership, quota '
            'coverage, and workload growth before expanding shared capacity.'
        ),
        priority='Warning',
        source='top_consumers_dominant_namespaces',
        resource='namespace',
        action_type='dominant_namespaces',
        href='/analytics/top-consumers?tab=records&focus=dominant_namespaces',
        icon='network',
    )


def _pvc_pressure_recommendation(
    facts: dict[str, Any],
) -> dict[str, Any] | None:
    rows = facts['high_pvc']
    if not rows:
        return None
    return build_recommendation(
        title='Clean Up or Expand High PVC Usage',
        description=(
            f'{len(rows)} PVC consumer row(s) are using at least 80% of observed '
            'volume capacity. Review cleanup, retention, expansion, and owning '
            'namespace before storage pressure becomes disruptive.'
        ),
        priority='Critical' if facts['critical_pvc'] else 'Warning',
        source='top_consumers_high_pvc',
        resource='storage',
        action_type='high_pvc',
        href='/analytics/top-consumers?tab=records&resource=pvc&focus=high_pvc',
        icon='database',
    )


def _evidence_recovery_recommendation(
    facts: dict[str, Any],
) -> dict[str, Any] | None:
    incomplete_resources = facts['incomplete_resources']
    if not incomplete_resources:
        return None
    return build_recommendation(
        title='Restore Multi-Resource Consumer Evidence',
        description=(
            f'{int(incomplete_resources)} resource evidence set(s) are partial or '
            'unavailable. Restore Prometheus coverage and capacity denominators '
            'before treating the page as a complete consumer baseline.'
        ),
        priority='Warning',
        source='top_consumers',
        source_label='Top Consumers Evidence Coverage',
        resource='consumer',
        action_type='evidence_recovery',
        href='/analytics/top-consumers?tab=rankings',
        icon='database-zap',
    )


def _top_consumers_baseline_recommendations() -> list[dict[str, Any]]:
    return [
        build_recommendation(
            title='No Critical Consumer Hotspot Detected',
            description=(
                'Complete CPU, memory, pod, and PVC evidence is currently below '
                'actionable consumer-pressure thresholds. Continue reviewing this '
                'page during incidents, deployments, and capacity reviews.'
            ),
            priority='Normal',
            source='top_consumers_baseline',
            resource='consumer',
            action_type='monitoring',
            href='/analytics/top-consumers?tab=rankings',
            icon='check-circle-2',
            is_actionable=False,
        ),
        build_recommendation(
            title='Review Top Consumers Periodically',
            description=(
                'Use Top Consumers as the first drilldown when utilization, '
                'capacity, or forecast pages show pressure.'
            ),
            priority='Info',
            source='top_consumers_practice',
            resource='consumer',
            action_type='review',
            href='/analytics/top-consumers?tab=recommendations',
            icon='scan-search',
            is_actionable=False,
        ),
    ]


def build_top_consumers_actionable_recommendations(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    consumer_payload = _top_consumers_payload(payload)
    if not isinstance(consumer_payload, dict):
        consumer_payload = {}
    facts = _top_consumers_recommendation_facts(consumer_payload)
    candidates = (
        _missing_request_recommendation(facts),
        _compute_pressure_recommendation(facts),
        _memory_limit_recommendation(facts),
        _dominant_namespace_recommendation(facts),
        _pvc_pressure_recommendation(facts),
        _evidence_recovery_recommendation(facts),
    )
    recommendations = deduplicate_recommendations(
        [candidate for candidate in candidates if candidate is not None]
    )
    return recommendations or _top_consumers_baseline_recommendations()


def get_top_consumer_dominant_namespaces(rows: list[Any]) -> list[str]:
    namespace_scores: dict[str, float] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        namespace = str(row.get('namespace', '') or '')
        if not namespace:
            continue

        contribution = get_numeric_value(row.get('contribution_percent', 0))
        risk_label = get_status_label(row.get('risk', '')).lower()

        if contribution < 20 and risk_label not in {'warning', 'critical'}:
            continue

        risk_weight = 10.0 if risk_label == 'critical' else 5.0 if risk_label == 'warning' else 0.0
        namespace_scores[namespace] = namespace_scores.get(namespace, 0.0) + contribution + risk_weight

    return [
        namespace
        for namespace, _score in sorted(
            namespace_scores.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )[:3]
    ]
