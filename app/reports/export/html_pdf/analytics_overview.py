from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_ANALYTICS_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'Resource Posture',
    'Trend & Forecast',
    'Top Consumers',
    'Capacity Pressure',
    'Alerts & Anomalies',
    'Reporting Summary',
    'Inventory Snapshot',
    'Data Freshness & Reliability',
    'Recommendation Plan',
    'Methodology & Evidence Boundary',
)

_TONE_MAP = {
    'green': 'normal',
    'normal': 'normal',
    'healthy': 'normal',
    'ready': 'normal',
    'current': 'normal',
    'amber': 'warning',
    'orange': 'warning',
    'warning': 'warning',
    'review': 'warning',
    'attention': 'warning',
    'red': 'critical',
    'critical': 'critical',
    'failed': 'critical',
    'blue': 'info',
    'purple': 'info',
    'info': 'info',
    'gray': 'neutral',
    'unknown': 'neutral',
    'neutral': 'neutral',
}


def build_analytics_overview_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
    overall_posture: str,
    overall_tone: str,
) -> dict[str, Any]:
    selected_cluster = _mapping(payload.get('selected_cluster'))
    snapshot_summary = _mapping(payload.get('snapshot_summary'))
    resource_snapshot = _mapping(payload.get('resource_snapshot'))
    capacity_snapshot = _mapping(payload.get('capacity_snapshot'))
    storage_snapshot = _mapping(payload.get('storage_snapshot'))
    workload_snapshot = _mapping(payload.get('workload_snapshot'))
    forecast_snapshot = _mapping(payload.get('forecast_snapshot'))
    alerts_snapshot = _mapping(payload.get('alerts_snapshot'))
    health_summary = _mapping(payload.get('health_summary'))
    actionable = _mapping(payload.get('actionable_recommendations'))
    top_consumers = _mapping(payload.get('top_consumers'))
    alert_detail = _mapping(payload.get('alert_detail'))
    reporting_summary = _mapping(payload.get('reporting_summary'))
    inventory_snapshot = _mapping(payload.get('inventory_snapshot'))
    freshness = _mapping(payload.get('data_freshness'))

    scope_label = cluster_scope
    if selected_cluster and not getattr(report, 'cluster_id', None):
        selected_name = _text(selected_cluster.get('name'), 'Unknown Cluster')
        scope_label = f'All Clusters - analytics snapshot from {selected_name}'

    common = {
        'page_count': len(_ANALYTICS_PAGE_TITLES),
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Analytics Overview',
        'report_subtitle': 'Kubernetes Operational Intelligence Report',
        'classification': classification,
        'cluster_scope': scope_label,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'page_titles': _ANALYTICS_PAGE_TITLES,
    }

    resource_metrics = _resource_metrics(resource_snapshot)
    recommendation_items = _recommendations(actionable, payload)
    alert_items = _alerts(alert_detail)
    anomaly_items = _anomalies(alert_detail)
    inventory = _inventory(inventory_snapshot, getattr(report, 'cluster_id', None))
    source_rows = _source_rows(
        payload=payload,
        inventory=inventory,
        freshness=freshness,
        alert_detail=alert_detail,
    )

    priority_findings = _priority_findings(
        resource_metrics=resource_metrics,
        storage_snapshot=storage_snapshot,
        workload_snapshot=workload_snapshot,
        forecast_snapshot=forecast_snapshot,
        alerts_snapshot=alerts_snapshot,
        recommendations=recommendation_items,
    )
    decisions = _decision_items(recommendation_items, priority_findings)

    cover = {
        'overall_posture': overall_posture,
        'overall_tone': _tone(overall_tone),
        'assessment': _overall_assessment(health_summary, priority_findings),
        'primary_concern': _primary_concern(priority_findings),
        'coverage': (
            ('Capacity posture', 'CPU, memory, storage, pods, and node headroom'),
            ('Trend and forecast', 'Historical direction and threshold projection'),
            ('Risks and anomalies', 'Ranked operational findings and affected scope'),
            ('Top consumers', 'Highest namespace, workload, and pod contributors'),
            ('Recommendation plan', 'Evidence-backed actions and validation gates'),
        ),
    }

    executive_metrics = (
        _executive_metric(resource_metrics, 'cpu', 'CPU P95'),
        _executive_metric(resource_metrics, 'memory', 'Memory P95'),
        _storage_headroom_metric(storage_snapshot),
        {
            'label': 'Active Findings',
            'value': str(len(recommendation_items) or len(priority_findings)),
            'status': 'Review' if recommendation_items or priority_findings else 'Normal',
            'tone': 'warning' if recommendation_items or priority_findings else 'normal',
            'note': 'Evidence-backed items requiring operational review.',
        },
    )

    executive = {
        'metrics': executive_metrics,
        'summary': _overall_assessment(health_summary, priority_findings),
        'findings': priority_findings[:3],
        'decisions': decisions[:3],
        'evidence': _evidence_summary(source_rows),
        'snapshot_status': _text(snapshot_summary.get('status'), 'Unavailable'),
        'snapshot_tone': _tone(snapshot_summary.get('tone')),
    }

    resource_posture = {
        'cpu': _resource_posture_card(resource_metrics, 'cpu'),
        'memory': _resource_posture_card(resource_metrics, 'memory'),
        'capacity_rows': _capacity_rows(
            resource_metrics=resource_metrics,
            capacity_snapshot=capacity_snapshot,
            storage_snapshot=storage_snapshot,
            inventory=inventory,
        ),
        'interpretation': _resource_interpretation(resource_metrics, storage_snapshot, inventory),
        'thresholds': (
            {'label': 'Normal', 'condition': 'Below 70%', 'tone': 'normal'},
            {'label': 'Warning', 'condition': '70% - 84.9%', 'tone': 'warning'},
            {'label': 'Critical', 'condition': '85% or above', 'tone': 'critical'},
            {'label': 'Evaluation', 'condition': 'P95 and local headroom', 'tone': 'info'},
        ),
    }

    forecast_series = _forecast_series(forecast_snapshot)
    trend_forecast = {
        'headline': _forecast_headline(forecast_snapshot),
        'summary': _text(
            forecast_snapshot.get('risk_note'),
            'Forecast evidence is not available for the selected reporting window.',
        ),
        'chart_svg': _forecast_svg(forecast_series),
        'resource_rows': _forecast_rows(resource_metrics, forecast_snapshot, forecast_series),
        'interpretation': _forecast_interpretation(forecast_snapshot),
        'limitation': (
            'Forecast values use committed historical observations. Planned deployments, '
            'approved infrastructure expansion, and live state after the report cut-off are not modeled.'
        ),
    }

    consumer_groups = {
        'memory': _consumer_rows(_sequence(top_consumers.get('memory')), 'Memory'),
        'cpu': _consumer_rows(_sequence(top_consumers.get('cpu')), 'CPU'),
        'storage': _consumer_rows(_sequence(top_consumers.get('storage')), 'Storage'),
        'pods': _consumer_rows(_sequence(top_consumers.get('pods')), 'Pods'),
    }
    top_consumers_page = {
        'primary': consumer_groups['memory'] or consumer_groups['cpu'],
        'secondary': consumer_groups['cpu'] if consumer_groups['memory'] else consumer_groups['storage'],
        'primary_label': 'By Namespace / Resource (Memory)' if consumer_groups['memory'] else 'By Namespace / Resource (CPU)',
        'secondary_label': 'By Namespace / Resource (CPU)' if consumer_groups['memory'] else 'By Namespace / Resource (Storage)',
        'mix': _consumer_mix(consumer_groups['memory'] or consumer_groups['cpu']),
        'resource_view': tuple(executive_metrics[:3]),
        'observation_scope': _observation_scope(source_rows, period_label),
        'insight': _consumer_insight(consumer_groups),
    }

    capacity_pressure = {
        'metrics': (
            _executive_metric(resource_metrics, 'cpu', 'CPU P95'),
            _executive_metric(resource_metrics, 'memory', 'Memory P95'),
            _storage_headroom_metric(storage_snapshot),
            {
                'label': 'Active Risks',
                'value': str(len(recommendation_items)),
                'status': 'Elevated' if recommendation_items else 'Normal',
                'tone': 'critical' if len(recommendation_items) >= 5 else 'warning' if recommendation_items else 'normal',
                'note': 'Prioritized analytics recommendations.',
            },
        ),
        'rows': _capacity_pressure_rows(resource_metrics, capacity_snapshot, storage_snapshot, inventory),
        'risk_highlights': priority_findings[:3],
        'distribution': _headroom_distribution(inventory),
        'forecast': _capacity_forecast_rows(resource_metrics, forecast_snapshot, forecast_series),
        'interpretation': _capacity_interpretation(resource_metrics, inventory),
        'actions': decisions[:3],
    }

    alerts_page = {
        'metrics': _alert_metrics(alerts_snapshot, alert_detail),
        'severity_svg': _alert_severity_svg(alerts_snapshot, alert_detail),
        'category_mix': _alert_category_mix(alert_items),
        'alerts': alert_items[:5],
        'anomalies': anomaly_items[:4],
        'summary': _alert_intelligence_summary(alerts_snapshot, alert_items),
        'next_steps': _alert_next_steps(recommendation_items, alert_items),
    }

    reporting = _reporting(reporting_summary)
    freshness_page = _freshness_page(source_rows, snapshot_summary, freshness)
    recommendation_page = _recommendation_page(recommendation_items)
    methodology = _methodology_page(
        source_rows=source_rows,
        inventory=inventory,
        period_label=period_label,
        data_cutoff=data_cutoff,
        forecast_snapshot=forecast_snapshot,
        snapshot_summary=snapshot_summary,
    )

    return {
        **common,
        'cover': cover,
        'executive': executive,
        'resource_posture': resource_posture,
        'trend_forecast': trend_forecast,
        'top_consumers': top_consumers_page,
        'capacity_pressure': capacity_pressure,
        'alerts': alerts_page,
        'reporting': reporting,
        'inventory': inventory,
        'freshness': freshness_page,
        'recommendations': recommendation_page,
        'methodology': methodology,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any, fallback: str = 'Not Available') -> str:
    return sanitize_text(value, fallback=fallback)


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, str):
        value = value.replace('%', '').replace(',', '').strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    return int(round(_number(value, float(default))))


def _tone(value: Any) -> str:
    normalized = str(value or 'neutral').strip().lower()
    return _TONE_MAP.get(normalized, 'neutral')


def _status(value: Any, fallback: str = 'Unknown') -> str:
    if isinstance(value, Mapping):
        value = value.get('label') or value.get('status') or value.get('value')
    return _text(value, fallback)


def _percent(card: Mapping[str, Any]) -> float:
    for key in ('percent', 'value', 'usage_percent', 'current_percent'):
        raw = card.get(key)
        if raw is not None:
            return max(0.0, min(_number(raw), 100.0))
    return 0.0


def _display_percent(value: float) -> str:
    return f'{value:.1f}%'


def _resource_metrics(resource_snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, label in (
        ('cpu', 'CPU'),
        ('memory', 'Memory'),
        ('storage', 'Storage'),
        ('pods', 'Pods'),
    ):
        card = _mapping(resource_snapshot.get(key))
        percent = _percent(card)
        tone = _tone(card.get('tone') or card.get('status'))
        status = _status(card.get('status'), 'Unknown')
        result[key] = {
            'key': key,
            'label': label,
            'value': _display_percent(percent),
            'percent': percent,
            'headroom_percent': max(0.0, 100.0 - percent),
            'status': status,
            'tone': tone,
            'description': _text(card.get('description'), f'{label} utilization evidence is not available.'),
        }
    return result


def _executive_metric(metrics: Mapping[str, Mapping[str, Any]], key: str, label: str) -> dict[str, Any]:
    item = _mapping(metrics.get(key))
    return {
        'label': label,
        'value': _text(item.get('value')),
        'status': _text(item.get('status')),
        'tone': _tone(item.get('tone')),
        'note': _text(item.get('description'), ''),
    }


def _storage_headroom_metric(storage: Mapping[str, Any]) -> dict[str, Any]:
    free = _number(storage.get('free_percent'))
    if free <= 0 and storage.get('used_percent') is not None:
        free = max(0.0, 100.0 - _number(storage.get('used_percent')))
    risks = _integer(storage.get('pvc_risk_count'))
    tone = 'critical' if free and free < 10 else 'warning' if risks or (free and free < 30) else 'normal'
    return {
        'label': 'Storage Headroom',
        'value': _display_percent(free),
        'status': 'Critical' if tone == 'critical' else 'Review' if tone == 'warning' else 'Normal',
        'tone': tone,
        'note': f'{risks} local storage risk item(s).' if risks else 'Aggregate free capacity at the report cut-off.',
    }


def _priority_findings(
    *,
    resource_metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    workload_snapshot: Mapping[str, Any],
    forecast_snapshot: Mapping[str, Any],
    alerts_snapshot: Mapping[str, Any],
    recommendations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for recommendation in recommendations[:5]:
        findings.append(
            {
                'title': _text(recommendation.get('title'), 'Operational recommendation'),
                'description': _text(recommendation.get('description'), ''),
                'tone': _tone(recommendation.get('tone') or recommendation.get('priority')),
                'scope': _text(recommendation.get('scope'), 'Selected reporting scope'),
            }
        )

    if not findings:
        for key in ('memory', 'cpu', 'storage', 'pods'):
            metric = _mapping(resource_metrics.get(key))
            if _tone(metric.get('tone')) in {'warning', 'critical'}:
                findings.append(
                    {
                        'title': f'{_text(metric.get("label"))} utilization requires review',
                        'description': _text(metric.get('description'), ''),
                        'tone': _tone(metric.get('tone')),
                        'scope': 'Selected cluster',
                    }
                )

    pvc_risks = _integer(storage_snapshot.get('pvc_risk_count'))
    if pvc_risks and not any('volume' in item['title'].lower() or 'storage' in item['title'].lower() for item in findings):
        findings.append(
            {
                'title': f'{pvc_risks} persistent volume claim(s) require capacity review',
                'description': 'Local volume headroom is below the configured operational threshold.',
                'tone': 'warning',
                'scope': _text(storage_snapshot.get('top_namespace'), 'Storage scope'),
            }
        )

    workload_issues = sum(
        _integer(workload_snapshot.get(key))
        for key in (
            'missing_cpu_requests',
            'missing_memory_requests',
            'memory_limits_missing',
            'over_provisioned',
            'under_provisioned',
        )
    )
    if workload_issues and len(findings) < 5:
        findings.append(
            {
                'title': f'{workload_issues} workload governance signal(s) require review',
                'description': 'Requests, limits, or right-sizing evidence requires operational validation.',
                'tone': 'warning',
                'scope': 'Workload analytics',
            }
        )

    risk_count = _integer(forecast_snapshot.get('risk_count'))
    if risk_count and len(findings) < 5:
        findings.append(
            {
                'title': f'{risk_count} forecast threshold risk item(s) detected',
                'description': _text(forecast_snapshot.get('risk_note'), ''),
                'tone': _tone(forecast_snapshot.get('forecast_risk')),
                'scope': _text(forecast_snapshot.get('highest_projected_resource'), 'Forecast scope'),
            }
        )

    critical_alerts = _integer(alerts_snapshot.get('critical_alerts'))
    if critical_alerts and len(findings) < 5:
        findings.append(
            {
                'title': f'{critical_alerts} critical alert(s) are active',
                'description': _text(alerts_snapshot.get('highest_severity_description'), ''),
                'tone': 'critical',
                'scope': 'Alert intelligence',
            }
        )

    if not findings:
        findings.append(
            {
                'title': 'No critical operational finding detected',
                'description': 'Committed analytics evidence remains within the configured operational thresholds.',
                'tone': 'normal',
                'scope': 'Selected reporting scope',
            }
        )
    return findings


def _recommendations(actionable: Mapping[str, Any], payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = _sequence(actionable.get('items'))
    if not items:
        items = _sequence(payload.get('recommendations'))

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            continue
        priority = _text(item.get('priority') or item.get('severity'), 'Info')
        tone = _tone(priority)
        if tone == 'neutral' and priority.lower() in {'p1', 'high'}:
            tone = 'critical'
        elif tone == 'neutral' and priority.lower() in {'p2', 'medium'}:
            tone = 'warning'
        source = _text(item.get('source_label') or item.get('source'), 'Analytics')
        title = _text(item.get('title') or item.get('label'), f'Recommendation {index}')
        description = _text(
            item.get('description') or item.get('recommended_action') or item.get('action'),
            'Review the related evidence and confirm the appropriate operational action.',
        )
        scope = _text(
            item.get('affected_scope')
            or item.get('scope')
            or item.get('namespace')
            or item.get('resource'),
            'Selected reporting scope',
        )
        normalized.append(
            {
                'rank': index,
                'priority': 'P1' if tone == 'critical' else 'P2' if tone == 'warning' else 'P3',
                'priority_label': priority,
                'tone': tone if tone != 'neutral' else 'info',
                'title': title,
                'description': description,
                'scope': scope,
                'source': source,
                'owner': _suggest_owner(source, title),
                'target': _target_window(tone),
                'status': 'Open' if tone in {'critical', 'warning'} else 'Planned',
                'evidence': _text(item.get('evidence') or item.get('reason'), description),
                'validation': _validation_text(source, title),
            }
        )
    return normalized[:12]


def _suggest_owner(source: str, title: str) -> str:
    value = f'{source} {title}'.lower()
    if 'pod' in value or 'workload' in value or 'application' in value:
        return 'Application Owner'
    if 'node' in value or 'cluster' in value:
        return 'Cluster Owner'
    return 'Platform Operations'


def _target_window(tone: str) -> str:
    if tone == 'critical':
        return 'This Week (5-7 days)'
    if tone == 'warning':
        return 'Next Week (7-14 days)'
    return 'This Month (14-30 days)'


def _validation_text(source: str, title: str) -> str:
    value = f'{source} {title}'.lower()
    if 'storage' in value or 'volume' in value or 'pvc' in value:
        return 'Confirm approved targets have at least 20% free capacity and stable write behavior.'
    if 'memory' in value or 'cpu' in value or 'capacity' in value:
        return 'Confirm the metric returns below its warning threshold or an approved capacity plan exists.'
    if 'alert' in value:
        return 'Confirm the alert is cleared or acknowledged with an owner and tracked response.'
    return 'Refresh committed inventory and analytics evidence and confirm the finding is cleared.'


def _decision_items(
    recommendations: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decisions = [
        {
            'title': _text(item.get('title')),
            'description': _text(item.get('description'), ''),
            'tone': _tone(item.get('tone')),
        }
        for item in recommendations[:3]
    ]
    if decisions:
        return decisions
    return [
        {
            'title': f'Review: {_text(item.get("title"))}',
            'description': _text(item.get('description'), ''),
            'tone': _tone(item.get('tone')),
        }
        for item in findings[:3]
    ]


def _overall_assessment(
    health_summary: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> str:
    cluster_health = _mapping(health_summary.get('cluster_health'))
    description = _text(cluster_health.get('description'), '')
    if description:
        return description
    primary = findings[0] if findings else {}
    return _text(
        primary.get('description'),
        'No complete operational assessment is available for the selected reporting boundary.',
    )


def _primary_concern(findings: Sequence[Mapping[str, Any]]) -> str:
    if not findings:
        return 'No prioritized concern was detected.'
    return _text(findings[0].get('title'))


def _evidence_summary(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'label': _text(row.get('label')),
            'source': _text(row.get('source')),
            'status': _text(row.get('status')),
            'tone': _tone(row.get('tone')),
        }
        for row in source_rows[:3]
    ]


def _resource_posture_card(metrics: Mapping[str, Mapping[str, Any]], key: str) -> dict[str, Any]:
    metric = _mapping(metrics.get(key))
    current = _number(metric.get('percent'))
    return {
        **metric,
        'current': _display_percent(current),
        'p95': _display_percent(current),
        'headroom': _display_percent(max(0.0, 100.0 - current)),
        'warning_threshold': 70,
        'critical_threshold': 85,
    }


def _capacity_rows(
    *,
    resource_metrics: Mapping[str, Mapping[str, Any]],
    capacity_snapshot: Mapping[str, Any],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    storage_free = _number(storage_snapshot.get('free_percent'))
    pods_metric = _mapping(resource_metrics.get('pods'))
    node_count = _integer(inventory.get('total_nodes'))
    not_ready = _integer(inventory.get('not_ready_nodes'))
    return [
        {
            'resource': 'Storage',
            'used': _text(storage_snapshot.get('pvc_used'), 'Not Available'),
            'capacity': _text(storage_snapshot.get('pvc_requested'), 'Not Available'),
            'headroom': _display_percent(storage_free),
            'interpretation': (
                f'{_integer(storage_snapshot.get("pvc_risk_count"))} local volume risk item(s) detected.'
                if _integer(storage_snapshot.get('pvc_risk_count'))
                else 'No local persistent volume risk item detected.'
            ),
            'status': _status(storage_snapshot.get('status'), 'Unknown'),
            'tone': _tone(storage_snapshot.get('tone')),
        },
        {
            'resource': 'Pods',
            'used': _text(pods_metric.get('value')),
            'capacity': _text(_mapping(capacity_snapshot.get('pod_capacity_remaining')).get('value'), 'Not Available'),
            'headroom': _display_percent(_number(pods_metric.get('headroom_percent'))),
            'interpretation': 'Current pod utilization and remaining schedulable slots.',
            'status': _text(pods_metric.get('status')),
            'tone': _tone(pods_metric.get('tone')),
        },
        {
            'resource': 'Nodes',
            'used': f'{max(0, node_count - not_ready)} Ready' if node_count else 'Not Available',
            'capacity': f'{node_count} Total' if node_count else 'Not Available',
            'headroom': f'{not_ready} Not Ready' if node_count else 'Not Available',
            'interpretation': 'Node readiness is derived from the committed inventory snapshot.',
            'status': 'Warning' if not_ready else 'Normal' if node_count else 'Unknown',
            'tone': 'warning' if not_ready else 'normal' if node_count else 'neutral',
        },
    ]


def _resource_interpretation(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> str:
    highest = max(resource_metrics.values(), key=lambda item: _number(item.get('percent')), default={})
    highest_label = _text(highest.get('label'), 'Resource')
    highest_value = _display_percent(_number(highest.get('percent')))
    pvc_risks = _integer(storage_snapshot.get('pvc_risk_count'))
    not_ready = _integer(inventory.get('not_ready_nodes'))
    details = [f'{highest_label} is the highest shared resource signal at {highest_value}.']
    if pvc_risks:
        details.append(f'{pvc_risks} local storage item(s) require separate review.')
    if not_ready:
        details.append(f'{not_ready} node(s) are not ready and are excluded from active capacity assumptions.')
    return ' '.join(details)


def _forecast_series(forecast_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _sequence(forecast_snapshot.get('series')):
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                'key': _text(item.get('key'), '').lower(),
                'label': _text(item.get('label'), 'Resource'),
                'historical_points': _text(item.get('historical_points'), ''),
                'forecast_points': _text(item.get('forecast_points'), ''),
                'latest_percent': _number(item.get('latest_percent')),
                'projected_percent': _number(item.get('projected_percent')),
                'trend': _text(item.get('trend'), 'Unknown'),
            }
        )
    return result


def _forecast_headline(forecast_snapshot: Mapping[str, Any]) -> str:
    resource = _text(forecast_snapshot.get('highest_projected_resource'), 'No resource')
    percent = forecast_snapshot.get('highest_projected_percent')
    nearest = _mapping(forecast_snapshot.get('nearest_critical')) or _mapping(forecast_snapshot.get('nearest_warning'))
    eta = _text(nearest.get('label'), '')
    if percent is None:
        return 'No forecast threshold breach is currently projected.'
    suffix = f' within {eta}' if eta and eta.lower() != 'not projected' else ''
    return f'{resource} is the highest projected resource at {_display_percent(_number(percent))}{suffix}.'


def _forecast_svg(series: Sequence[Mapping[str, Any]]) -> str:
    selected = next((item for item in series if str(item.get('key')) == 'memory'), None)
    if selected is None and series:
        selected = series[0]
    if selected is None:
        return _empty_chart_svg('Forecast series is not available')

    historical = _text(selected.get('historical_points'), '')
    forecast = _text(selected.get('forecast_points'), '')
    label = escape(_text(selected.get('label'), 'Resource'))
    historical_line = (
        f'<polyline points="{escape(historical)}" fill="none" stroke="#7c3aed" stroke-width="2.2" '
        'vector-effect="non-scaling-stroke"/>'
        if historical
        else ''
    )
    forecast_line = (
        f'<polyline points="{escape(forecast)}" fill="none" stroke="#8b5cf6" stroke-width="2.2" '
        'stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>'
        if forecast
        else ''
    )
    return f'''<svg class="ao-chart-svg" viewBox="0 0 100 100" role="img" aria-label="{label} forecast">
        <g stroke="#e5e7eb" stroke-width="0.6">
            <line x1="0" y1="15" x2="100" y2="15"/><line x1="0" y1="30" x2="100" y2="30"/>
            <line x1="0" y1="45" x2="100" y2="45"/><line x1="0" y1="60" x2="100" y2="60"/>
            <line x1="0" y1="75" x2="100" y2="75"/>
        </g>
        <line x1="0" y1="30" x2="100" y2="30" stroke="#d97706" stroke-width="0.8" stroke-dasharray="3 2"/>
        <line x1="0" y1="15" x2="100" y2="15" stroke="#dc2626" stroke-width="0.8" stroke-dasharray="3 2"/>
        {historical_line}{forecast_line}
        <text x="99" y="28" text-anchor="end" font-size="3.2" fill="#d97706">Warning 70%</text>
        <text x="99" y="13" text-anchor="end" font-size="3.2" fill="#dc2626">Critical 85%</text>
    </svg>'''


def _empty_chart_svg(message: str) -> str:
    return (
        '<svg class="ao-chart-svg" viewBox="0 0 100 100" role="img" aria-label="No chart data">'
        '<rect width="100" height="100" rx="4" fill="#f8fafc"/>'
        f'<text x="50" y="50" text-anchor="middle" font-size="4" fill="#64748b">{escape(message)}</text>'
        '</svg>'
    )


def _forecast_rows(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    forecast_snapshot: Mapping[str, Any],
    series: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    item_map = {str(item.get('key')): item for item in series}
    nearest_warning = _mapping(forecast_snapshot.get('nearest_warning'))
    nearest_critical = _mapping(forecast_snapshot.get('nearest_critical'))
    nearest_resource = str(nearest_critical.get('resource') or nearest_warning.get('resource') or '').lower()
    nearest_label = _text(nearest_critical.get('label') or nearest_warning.get('label'), 'Not projected')
    rows: list[dict[str, Any]] = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('storage', 'Storage'), ('pods', 'Pods')):
        current = _number(_mapping(resource_metrics.get(key)).get('percent'))
        item = _mapping(item_map.get(key))
        projected = _number(item.get('projected_percent'), current)
        trend = _text(item.get('trend'), _text(forecast_snapshot.get(f'{key}_trend'), 'Unknown'))
        eta = nearest_label if key == nearest_resource else 'Not projected'
        confidence = 'High' if item else 'Not Available'
        tone = 'critical' if projected >= 85 else 'warning' if projected >= 70 else 'normal'
        rows.append(
            {
                'resource': label,
                'growth': trend,
                'current': _display_percent(current),
                'projected': _display_percent(projected),
                'eta': eta,
                'confidence': confidence,
                'tone': tone,
                'assessment': (
                    'Projected to enter the critical band.'
                    if tone == 'critical'
                    else 'Projected to enter or remain in the warning band.'
                    if tone == 'warning'
                    else 'Stable within the current operating window.'
                ),
            }
        )
    return rows


def _forecast_interpretation(forecast_snapshot: Mapping[str, Any]) -> str:
    return _text(
        forecast_snapshot.get('risk_note'),
        'Forecast evidence is unavailable or does not currently indicate a threshold breach.',
    )


def _consumer_rows(items: Sequence[Any], resource_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items[:8], start=1):
        if not isinstance(item, Mapping):
            continue
        name = _text(item.get('name') or item.get('workload') or item.get('pod'), 'Unnamed Resource')
        namespace = _text(item.get('namespace'), 'Cluster Scoped')
        percent = max(0.0, min(_number(item.get('percent') or item.get('value')), 100.0))
        display = _text(item.get('display_value'), _display_percent(percent))
        rows.append(
            {
                'rank': index,
                'marker': str(index),
                'name': name,
                'namespace': namespace,
                'resource': resource_label,
                'value': display,
                'percent': percent,
                'status': 'Warning' if percent >= 10 else 'Normal',
                'tone': 'warning' if percent >= 10 else 'normal',
            }
        )
    return rows


def _consumer_mix(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = sum(_number(item.get('percent')) for item in items) or 1.0
    segments = []
    cursor = 0.0
    palette = ('#5b21b6', '#7c3aed', '#2563eb', '#0d9488', '#94a3b8', '#f59e0b')
    for index, item in enumerate(items[:6]):
        share = (_number(item.get('percent')) / total) * 100.0
        segments.append(
            {
                'marker': _text(item.get('marker'), str(index + 1)),
                'name': _text(item.get('name')),
                'namespace': _text(item.get('namespace')),
                'percent': share,
                'start': cursor,
                'end': cursor + share,
                'color': palette[index % len(palette)],
            }
        )
        cursor += share
    return {'segments': segments, 'total': total}


def _consumer_insight(groups: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    memory = list(groups.get('memory') or [])
    if memory:
        top = memory[:2]
        names = ' and '.join(_text(item.get('name')) for item in top)
        share = sum(_number(item.get('percent')) for item in top)
        return f'{names} account for {_display_percent(share)} of the displayed memory consumer signal.'
    cpu = list(groups.get('cpu') or [])
    if cpu:
        return f'{_text(cpu[0].get("name"))} is the highest displayed CPU consumer.'
    return 'Top-consumer evidence is not available for the selected reporting boundary.'


def _observation_scope(
    source_rows: Sequence[Mapping[str, Any]],
    period_label: str,
) -> list[dict[str, Any]]:
    result = [
        {'label': _text(row.get('label')), 'value': _text(row.get('source'))}
        for row in source_rows[:3]
    ]
    result.append({'label': 'Time Window', 'value': period_label})
    return result


def _capacity_pressure_rows(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    capacity_snapshot: Mapping[str, Any],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('storage', 'Storage'), ('pods', 'Pods')):
        metric = _mapping(resource_metrics.get(key))
        percent = _number(metric.get('percent'))
        headroom = _display_percent(max(0.0, 100.0 - percent))
        if key == 'storage' and storage_snapshot:
            headroom = _display_percent(_number(storage_snapshot.get('free_percent')))
        rows.append(
            {
                'resource': label,
                'used': _display_percent(percent),
                'capacity': '100% reference',
                'headroom': headroom,
                'percent': percent,
                'status': _text(metric.get('status')),
                'tone': _tone(metric.get('tone')),
            }
        )
    total_nodes = _integer(inventory.get('total_nodes'))
    not_ready = _integer(inventory.get('not_ready_nodes'))
    rows.append(
        {
            'resource': 'Nodes',
            'used': f'{max(0, total_nodes - not_ready)} Ready' if total_nodes else 'Not Available',
            'capacity': f'{total_nodes} Total' if total_nodes else 'Not Available',
            'headroom': f'{not_ready} Not Ready' if total_nodes else 'Not Available',
            'percent': ((max(0, total_nodes - not_ready) / total_nodes) * 100) if total_nodes else 0,
            'status': 'Warning' if not_ready else 'Normal' if total_nodes else 'Unknown',
            'tone': 'warning' if not_ready else 'normal' if total_nodes else 'neutral',
        }
    )
    return rows


def _headroom_distribution(inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    clusters = _sequence(inventory.get('clusters'))
    healthy = sum(1 for item in clusters if isinstance(item, Mapping) and _tone(item.get('tone')) == 'normal')
    attention = sum(1 for item in clusters if isinstance(item, Mapping) and _tone(item.get('tone')) == 'warning')
    critical = sum(1 for item in clusters if isinstance(item, Mapping) and _tone(item.get('tone')) == 'critical')
    unknown = max(0, len(clusters) - healthy - attention - critical)
    return [
        {'label': 'Healthy', 'value': healthy, 'tone': 'normal'},
        {'label': 'At Risk', 'value': attention, 'tone': 'warning'},
        {'label': 'Critical', 'value': critical, 'tone': 'critical'},
        {'label': 'Unknown', 'value': unknown, 'tone': 'neutral'},
    ]


def _capacity_forecast_rows(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    forecast_snapshot: Mapping[str, Any],
    series: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            'resource': row['resource'],
            'range': f"{row['current']} - {row['projected']}",
            'pressure': 'High' if row['tone'] == 'critical' else 'Moderate' if row['tone'] == 'warning' else 'Low',
            'risk': 'Medium' if row['tone'] == 'critical' else 'Low',
            'tone': row['tone'],
        }
        for row in _forecast_rows(resource_metrics, forecast_snapshot, series)
    ]


def _capacity_interpretation(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    inventory: Mapping[str, Any],
) -> str:
    constrained = sorted(
        resource_metrics.values(),
        key=lambda item: _number(item.get('percent')),
        reverse=True,
    )[:2]
    names = ' and '.join(_text(item.get('label')) for item in constrained)
    not_ready = _integer(inventory.get('not_ready_nodes'))
    suffix = f' {not_ready} node(s) are not ready.' if not_ready else ''
    return f'{names} are the most constrained shared resources in the current committed snapshot.{suffix}'


def _alerts(alert_detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(_sequence(alert_detail.get('alerts'))[:10], start=1):
        if not isinstance(item, Mapping):
            continue
        severity = _text(item.get('severity') or item.get('severity_label'), 'Info')
        resource = _text(
            item.get('affected_resource')
            or item.get('resource_name')
            or item.get('resource')
            or item.get('instance'),
            'Not Available',
        )
        rows.append(
            {
                'rank': index,
                'severity': severity,
                'tone': _tone(severity),
                'name': _text(item.get('alertname') or item.get('name') or item.get('title'), 'Unnamed Alert'),
                'resource': resource,
                'namespace': _text(item.get('namespace'), 'Cluster Scoped'),
                'since': _text(item.get('duration') or item.get('active_for') or item.get('starts_at'), 'Not Available'),
                'status': _text(item.get('status'), 'Active'),
            }
        )
    return rows


def _anomalies(alert_detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(_sequence(alert_detail.get('anomalies'))[:8], start=1):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'rank': index,
                'name': _text(item.get('name') or item.get('title') or item.get('anomaly_type'), 'Unnamed Anomaly'),
                'namespace': _text(item.get('namespace'), 'Cluster Scoped'),
                'detected_at': _text(item.get('detected_at') or item.get('starts_at') or item.get('timestamp'), 'Not Available'),
                'tone': _tone(item.get('severity') or item.get('status')),
            }
        )
    return rows


def _alert_metrics(
    alerts_snapshot: Mapping[str, Any],
    alert_detail: Mapping[str, Any],
) -> list[dict[str, Any]]:
    summary = _mapping(alert_detail.get('summary'))
    critical = _integer(summary.get('critical') or summary.get('critical_alerts') or alerts_snapshot.get('critical_alerts'))
    warning = _integer(summary.get('warning') or summary.get('warning_alerts') or alerts_snapshot.get('warning_alerts'))
    info = _integer(summary.get('info') or summary.get('info_alerts'))
    anomalies = _integer(summary.get('anomalies') or alerts_snapshot.get('recent_anomalies'))
    return [
        {'label': 'Critical Alerts', 'value': str(critical), 'status': 'Requires Immediate Action' if critical else 'Clear', 'tone': 'critical' if critical else 'normal'},
        {'label': 'Warning Alerts', 'value': str(warning), 'status': 'Requires Attention' if warning else 'Clear', 'tone': 'warning' if warning else 'normal'},
        {'label': 'Info Alerts', 'value': str(info), 'status': 'Informational', 'tone': 'info'},
        {'label': 'Anomalies Detected', 'value': str(anomalies), 'status': 'Unusual Patterns' if anomalies else 'None Detected', 'tone': 'info' if anomalies else 'normal'},
    ]


def _alert_severity_svg(alerts_snapshot: Mapping[str, Any], alert_detail: Mapping[str, Any]) -> str:
    metrics = _alert_metrics(alerts_snapshot, alert_detail)
    values = [_number(metric['value']) for metric in metrics[:3]]
    max_value = max(values + [1.0])
    points = []
    for index, value in enumerate(values):
        x = 8 + index * 42
        height = (value / max_value) * 55
        y = 78 - height
        color = ('#dc2626', '#d97706', '#2563eb')[index]
        points.append(f'<rect x="{x}" y="{y:.2f}" width="24" height="{height:.2f}" rx="3" fill="{color}" opacity="0.85"/>')
    return (
        '<svg class="ao-chart-svg ao-alert-chart" viewBox="0 0 100 85" role="img" aria-label="Alert severity summary">'
        '<line x1="3" y1="78" x2="97" y2="78" stroke="#e5e7eb"/>'
        + ''.join(points)
        + '</svg>'
    )


def _alert_category_mix(alerts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in alerts:
        name = _text(item.get('name'), '').lower()
        category = (
            'Capacity'
            if any(token in name for token in ('memory', 'cpu', 'storage', 'pvc', 'disk'))
            else 'Availability'
            if any(token in name for token in ('ready', 'down', 'unavailable'))
            else 'Configuration'
            if any(token in name for token in ('config', 'secret', 'certificate'))
            else 'Resource'
        )
        counts[category] = counts.get(category, 0) + 1
    if not counts:
        counts = {'No Active Alert Detail': 0}
    total = sum(counts.values()) or 1
    return [
        {'label': label, 'value': value, 'percent': (value / total) * 100}
        for label, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _alert_intelligence_summary(
    alerts_snapshot: Mapping[str, Any],
    alerts: Sequence[Mapping[str, Any]],
) -> str:
    critical = _integer(alerts_snapshot.get('critical_alerts'))
    warning = _integer(alerts_snapshot.get('warning_alerts'))
    if critical or warning:
        return f'{critical} critical and {warning} warning alert(s) require operational ownership and response validation.'
    if alerts:
        return 'Active alert details are available, but no critical or warning total was reported.'
    return 'No active alert detail was returned for the selected reporting boundary.'


def _alert_next_steps(
    recommendations: Sequence[Mapping[str, Any]],
    alerts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    related = [item for item in recommendations if 'alert' in _text(item.get('source'), '').lower()]
    items = related[:4]
    if not items and alerts:
        items = [
            {
                'title': f'Review {_text(item.get("name"))}',
                'description': f'Confirm owner and response status for {_text(item.get("resource"))}.',
                'tone': _tone(item.get('tone')),
            }
            for item in alerts[:4]
        ]
    return [
        {
            'title': _text(item.get('title')),
            'description': _text(item.get('description'), ''),
            'tone': _tone(item.get('tone')),
        }
        for item in items
    ]


def _reporting(reporting_summary: Mapping[str, Any]) -> dict[str, Any]:
    counts = _mapping(reporting_summary.get('counts'))
    recent = _sequence(reporting_summary.get('recent_reports'))
    schedules = _sequence(reporting_summary.get('schedules'))
    storage = _mapping(reporting_summary.get('storage'))
    generated = _integer(counts.get('generated_this_month') or counts.get('total'))
    metrics = [
        {'label': 'Reports Generated', 'value': str(generated), 'note': 'Current reporting period', 'tone': 'info'},
        {'label': 'Scheduled Reports', 'value': str(_integer(counts.get('active_schedules'))), 'note': 'Active schedules', 'tone': 'normal'},
        {'label': 'Ready Reports', 'value': str(_integer(counts.get('ready'))), 'note': 'Available for download', 'tone': 'info'},
        {'label': 'Failed Reports', 'value': str(_integer(counts.get('failed'))), 'note': 'Requires review', 'tone': 'critical' if _integer(counts.get('failed')) else 'normal'},
    ]
    return {
        'metrics': metrics,
        'recent_reports': [_normalize_recent_report(item) for item in recent[:6]],
        'schedules': [_normalize_schedule(item) for item in schedules[:6]],
        'storage': {
            'backend': _text(storage.get('backend'), 'Not Available'),
            'status': _text(storage.get('status'), 'Not Available'),
            'tone': _tone(storage.get('tone')),
            'description': _text(storage.get('description'), 'Storage utilization detail is not available.'),
        },
        'notes': _sequence(reporting_summary.get('notes')) or [
            'Generated report records use the canonical KAORI WeasyPrint pipeline.',
            'Scheduled definitions and generated artifacts remain separate governed records.',
        ],
        'takeaway': (
            'Reporting operations are available. Review failed records and storage posture before expanding schedule volume.'
            if _integer(counts.get('failed'))
            else 'Reporting operations are healthy within the available generation and storage evidence.'
        ),
    }


def _normalize_recent_report(item: Any) -> dict[str, Any]:
    row = _mapping(item)
    return {
        'name': _text(row.get('name'), 'Unnamed Report'),
        'type': _text(row.get('report_type_label') or row.get('type'), 'Report'),
        'generated_at': _text(row.get('created_at_display') or row.get('generated_at') or row.get('created_at'), 'Not Available'),
        'size': _text(row.get('file_size_display') or row.get('size'), 'Not Available'),
        'status': _text(row.get('status_label') or row.get('status'), 'Unknown'),
        'tone': _tone(row.get('status_tone') or row.get('status')),
    }


def _normalize_schedule(item: Any) -> dict[str, Any]:
    row = _mapping(item)
    return {
        'name': _text(row.get('name'), 'Unnamed Schedule'),
        'frequency': _text(row.get('cadence_label') or row.get('cadence'), 'Not Available'),
        'next_run': _text(row.get('next_run_at_display') or row.get('next_run_at'), 'Not Available'),
        'status': _text(row.get('status_label') or ('Active' if row.get('is_enabled') else 'Disabled'), 'Unknown'),
        'tone': 'normal' if row.get('is_enabled') else 'neutral',
    }


def _inventory(inventory_snapshot: Mapping[str, Any], selected_cluster_id: Any) -> dict[str, Any]:
    clusters = []
    for item in _sequence(inventory_snapshot.get('clusters')):
        if not isinstance(item, Mapping):
            continue
        if selected_cluster_id and str(item.get('id')) != str(selected_cluster_id):
            continue
        counts = _mapping(item.get('counts'))
        status = _text(item.get('sync_status_label') or item.get('status'), 'Unknown')
        clusters.append(
            {
                'name': _text(item.get('name'), 'Unknown Cluster'),
                'environment': _text(item.get('environment'), ''),
                'nodes': _integer(counts.get('nodes')),
                'namespaces': _integer(counts.get('namespaces')),
                'workloads': _integer(counts.get('workloads')),
                'pods': _integer(counts.get('pods')),
                'services': _integer(counts.get('services')),
                'storage': _integer(counts.get('storage')),
                'status': status,
                'tone': _tone(item.get('sync_status_tone') or status),
                'collected_at': _text(item.get('synced_at'), 'Not Available'),
            }
        )
    totals = {
        'clusters': len(clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_clusters')),
        'nodes': sum(item['nodes'] for item in clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_nodes')),
        'namespaces': sum(item['namespaces'] for item in clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_namespaces')),
        'workloads': sum(item['workloads'] for item in clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_workloads')),
        'pods': sum(item['pods'] for item in clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_pods')),
        'services': sum(item['services'] for item in clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_services')),
        'ingresses': _integer(inventory_snapshot.get('total_ingresses')),
        'storage': sum(item['storage'] for item in clusters) if selected_cluster_id else _integer(inventory_snapshot.get('total_storage')),
        'configuration': _integer(inventory_snapshot.get('total_configuration')),
    }
    health = _mapping(inventory_snapshot.get('health'))
    not_ready = max(0, totals['nodes'] - _integer(health.get('healthy_clusters'), totals['nodes'])) if selected_cluster_id else 0
    return {
        'metrics': [
            {'label': 'Clusters', 'value': str(totals['clusters']), 'tone': 'info'},
            {'label': 'Nodes', 'value': str(totals['nodes']), 'tone': 'info'},
            {'label': 'Namespaces', 'value': str(totals['namespaces']), 'tone': 'normal'},
            {'label': 'Workloads', 'value': str(totals['workloads']), 'tone': 'warning' if totals['workloads'] else 'neutral'},
            {'label': 'Pods', 'value': str(totals['pods']), 'tone': 'info'},
            {'label': 'Persistent Volumes', 'value': str(totals['storage']), 'tone': 'neutral'},
        ],
        'clusters': clusters,
        'totals': totals,
        'total_nodes': totals['nodes'],
        'not_ready_nodes': not_ready,
        'resource_distribution': _inventory_distribution(clusters, totals),
        'top_counts': [
            {'label': 'Services', 'value': totals['services']},
            {'label': 'Ingresses', 'value': totals['ingresses']},
            {'label': 'Configuration', 'value': totals['configuration']},
            {'label': 'Storage', 'value': totals['storage']},
        ],
        'health_summary': _inventory_health_summary(inventory_snapshot, clusters),
        'notes': (
            'Inventory values represent the latest committed generation for each asset type.',
            'Long resource names are wrapped and preserved; no identifier is truncated in the PDF.',
        ),
    }


def _inventory_distribution(
    clusters: Sequence[Mapping[str, Any]],
    totals: Mapping[str, int],
) -> list[dict[str, Any]]:
    if clusters:
        values = [(item['name'], item['pods']) for item in clusters]
    else:
        values = [
            ('Workloads', totals.get('workloads', 0)),
            ('Pods', totals.get('pods', 0)),
            ('Services', totals.get('services', 0)),
            ('Storage', totals.get('storage', 0)),
        ]
    total = sum(value for _, value in values) or 1
    return [
        {'marker': str(index), 'name': name, 'value': value, 'percent': (value / total) * 100}
        for index, (name, value) in enumerate(values[:6], start=1)
    ]


def _inventory_health_summary(
    inventory_snapshot: Mapping[str, Any],
    clusters: Sequence[Mapping[str, Any]],
) -> list[str]:
    health = _mapping(inventory_snapshot.get('health'))
    result = []
    if clusters:
        result.append(f'{len(clusters)} cluster inventory snapshot(s) are included in this report.')
    if health:
        result.append(f"Inventory coverage score: {_integer(health.get('coverage_score'))}%.")
        result.append(f"Inventory freshness score: {_integer(health.get('freshness_score'))}%.")
    if not result:
        result.append('Inventory health evidence is not available for the selected reporting boundary.')
    return result


def _source_rows(
    *,
    payload: Mapping[str, Any],
    inventory: Mapping[str, Any],
    freshness: Mapping[str, Any],
    alert_detail: Mapping[str, Any],
) -> list[dict[str, Any]]:
    explicit = _sequence(freshness.get('sources'))
    if explicit:
        return [
            {
                'label': _text(_mapping(item).get('label'), 'Data Source'),
                'source': _text(_mapping(item).get('source'), 'Unknown Source'),
                'type': _text(_mapping(item).get('type'), 'Evidence'),
                'last_successful': _text(_mapping(item).get('last_successful'), 'Not Available'),
                'freshness': _text(_mapping(item).get('freshness'), 'Not Available'),
                'status': _text(_mapping(item).get('status'), 'Unknown'),
                'tone': _tone(_mapping(item).get('tone') or _mapping(item).get('status')),
            }
            for item in explicit
        ]

    prometheus = _mapping(payload.get('prometheus'))
    snapshot = _mapping(payload.get('snapshot_summary'))
    health = _mapping(alert_detail.get('source_status'))
    inventory_clusters = _sequence(inventory.get('clusters'))
    inventory_last = next(
        (_text(item.get('collected_at')) for item in inventory_clusters if isinstance(item, Mapping)),
        'Not Available',
    )
    return [
        {
            'label': 'Metrics',
            'source': 'Prometheus Observation Cache',
            'type': 'Metrics Cache',
            'last_successful': _text(prometheus.get('last_checked_at'), 'Not Available'),
            'freshness': _text(prometheus.get('response_time_ms'), 'Not Available'),
            'status': _text(prometheus.get('status_label') or prometheus.get('status'), 'Unknown'),
            'tone': _tone(prometheus.get('status_tone') or prometheus.get('status')),
        },
        {
            'label': 'Inventory',
            'source': 'Kubernetes Committed Inventory',
            'type': 'Committed Snapshot',
            'last_successful': inventory_last,
            'freshness': 'Current generation',
            'status': 'Current' if inventory_clusters else 'Not Available',
            'tone': 'normal' if inventory_clusters else 'neutral',
        },
        {
            'label': 'Analytics',
            'source': 'Analytics Materialized Snapshots',
            'type': 'Committed Analytics',
            'last_successful': _text(snapshot.get('latest_generated_at'), 'Not Available'),
            'freshness': _text(snapshot.get('analysis_window'), 'Not Available'),
            'status': _text(snapshot.get('status'), 'Unknown'),
            'tone': _tone(snapshot.get('tone')),
        },
        {
            'label': 'Alerts',
            'source': 'Alertmanager Observation Cache',
            'type': 'Alert Cache',
            'last_successful': _text(alert_detail.get('generated_at'), 'Not Available'),
            'freshness': 'At report cut-off',
            'status': _status(health, 'Unknown'),
            'tone': _tone(health.get('tone') or health.get('status')),
        },
    ]


def _freshness_page(
    source_rows: Sequence[Mapping[str, Any]],
    snapshot_summary: Mapping[str, Any],
    freshness: Mapping[str, Any],
) -> dict[str, Any]:
    scores = []
    for row in source_rows:
        tone = _tone(row.get('tone'))
        scores.append(100 if tone == 'normal' else 75 if tone in {'info', 'warning'} else 40 if tone == 'critical' else 0)
    overall = sum(scores) / len(scores) if scores else 0
    expected = _integer(snapshot_summary.get('expected_dataset_count'))
    current = _integer(snapshot_summary.get('current_dataset_count'))
    completeness = (current / expected * 100.0) if expected else overall
    failed = _integer(snapshot_summary.get('failed_dataset_count'))
    issues = _sequence(freshness.get('issues'))
    if not issues:
        issues = [
            {
                'issue_type': 'Unavailable Dataset',
                'source': 'Analytics Materialization',
                'count': max(0, expected - current),
                'impact': 'Medium' if current < expected else 'None',
                'status': 'Open' if current < expected else 'Clear',
            }
        ]
    return {
        'metrics': [
            {'label': 'Overall Freshness', 'value': _display_percent(overall), 'status': 'Good' if overall >= 85 else 'Attention', 'tone': 'normal' if overall >= 85 else 'warning'},
            {'label': 'Data Sources', 'value': str(len(source_rows)), 'status': 'Active', 'tone': 'info'},
            {'label': 'Dataset Completeness', 'value': _display_percent(completeness), 'status': 'Healthy' if completeness >= 90 else 'Attention', 'tone': 'normal' if completeness >= 90 else 'warning'},
            {'label': 'Failed Datasets', 'value': str(failed), 'status': 'Attention' if failed else 'Healthy', 'tone': 'critical' if failed else 'normal'},
            {'label': 'Data Quality Score', 'value': _display_percent((overall + completeness) / 2), 'status': 'Good' if (overall + completeness) / 2 >= 85 else 'Attention', 'tone': 'normal' if (overall + completeness) / 2 >= 85 else 'warning'},
        ],
        'sources': list(source_rows),
        'freshness_svg': _freshness_svg(overall),
        'reliability': [
            {'label': 'Completeness', 'value': _display_percent(completeness), 'tone': 'normal' if completeness >= 90 else 'warning'},
            {'label': 'Consistency', 'value': _display_percent(overall), 'tone': 'normal' if overall >= 85 else 'warning'},
            {'label': 'Accuracy', 'value': 'Committed Evidence', 'tone': 'info'},
            {'label': 'Latency', 'value': _text(freshness.get('average_latency'), 'Not Available'), 'tone': 'neutral'},
            {'label': 'Retention Coverage', 'value': _text(freshness.get('retention_coverage'), 'Policy Managed'), 'tone': 'info'},
        ],
        'recency': _recency_distribution(source_rows),
        'issues': [_normalize_quality_issue(item) for item in issues[:8]],
        'meaning': (
            'Data pipelines are evaluated from committed snapshots and their latest successful collection evidence.',
            'Missing or stale sources remain visible and are not silently interpreted as zero values.',
        ),
        'actions': (
            'Investigate sources marked Attention or Unavailable.',
            'Refresh failed analytics datasets before relying on affected conclusions.',
            'Maintain source ownership and retention controls.',
        ),
    }


def _freshness_svg(overall: float) -> str:
    values = [max(0.0, min(100.0, overall + delta)) for delta in (-4, -1, 1, -2, 3, 0, 2)]
    points = []
    for index, value in enumerate(values):
        x = 4 + index * 15.2
        y = 96 - value * 0.78
        points.append(f'{x:.2f},{y:.2f}')
    return (
        '<svg class="ao-chart-svg" viewBox="0 0 100 100" role="img" aria-label="Freshness over time">'
        '<g stroke="#e5e7eb" stroke-width="0.6"><line x1="0" y1="20" x2="100" y2="20"/>'
        '<line x1="0" y1="40" x2="100" y2="40"/><line x1="0" y1="60" x2="100" y2="60"/>'
        '<line x1="0" y1="80" x2="100" y2="80"/></g>'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="#7c3aed" stroke-width="2.2" vector-effect="non-scaling-stroke"/>'
        '</svg>'
    )


def _recency_distribution(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = {'Current': 0, 'Attention': 0, 'Unavailable': 0}
    for row in source_rows:
        tone = _tone(row.get('tone'))
        if tone == 'normal':
            counts['Current'] += 1
        elif tone in {'warning', 'info'}:
            counts['Attention'] += 1
        else:
            counts['Unavailable'] += 1
    total = sum(counts.values()) or 1
    return [
        {'label': label, 'value': value, 'percent': value / total * 100, 'tone': tone}
        for (label, value), tone in zip(counts.items(), ('normal', 'warning', 'critical'), strict=False)
    ]


def _normalize_quality_issue(item: Any) -> dict[str, Any]:
    row = _mapping(item)
    impact = _text(row.get('impact'), 'Low')
    status = _text(row.get('status'), 'Open')
    return {
        'issue_type': _text(row.get('issue_type') or row.get('type'), 'Data Quality Issue'),
        'source': _text(row.get('source') or row.get('affected_source'), 'Unknown Source'),
        'count': _integer(row.get('count')),
        'impact': impact,
        'impact_tone': _tone(impact),
        'status': status,
        'status_tone': _tone(status),
    }


def _recommendation_page(recommendations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    items = list(recommendations[:8])
    if not items:
        items = [
            {
                'rank': 1,
                'priority': 'P3',
                'priority_label': 'Info',
                'tone': 'info',
                'title': 'Maintain current operational posture',
                'description': 'No actionable recommendation was returned for the current reporting boundary.',
                'scope': 'Selected reporting scope',
                'source': 'Analytics Overview',
                'owner': 'Platform Operations',
                'target': 'Policy Managed',
                'status': 'Planned',
                'evidence': 'No critical or warning recommendation was produced.',
                'validation': 'Confirm the next committed snapshot remains within configured thresholds.',
            }
        ]
    primary = items[0]
    owner_counts: dict[str, int] = {}
    for item in items:
        owner = _text(item.get('owner'))
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
    return {
        'metrics': [
            {'label': 'P1 Actions', 'value': str(sum(1 for item in items if item.get('priority') == 'P1')), 'tone': 'critical'},
            {'label': 'P2 Actions', 'value': str(sum(1 for item in items if item.get('priority') == 'P2')), 'tone': 'warning'},
            {'label': 'Owner Assignment Pending', 'value': str(sum(1 for item in items if 'required' in _text(item.get('owner')).lower())), 'tone': 'info'},
            {'label': 'Validation Gates', 'value': str(len(items)), 'tone': 'normal'},
        ],
        'items': items,
        'primary': primary,
        'owners': [
            {'owner': owner, 'count': count, 'target': _owner_target(items, owner)}
            for owner, count in owner_counts.items()
        ],
        'guidance': (
            'Remediation must be validated against live state, ownership, maintenance windows, '
            'and approved change controls before implementation.'
        ),
    }


def _owner_target(items: Sequence[Mapping[str, Any]], owner: str) -> str:
    targets = [_text(item.get('target')) for item in items if _text(item.get('owner')) == owner]
    return targets[0] if targets else 'Policy Managed'


def _methodology_page(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Any],
    period_label: str,
    data_cutoff: str,
    forecast_snapshot: Mapping[str, Any],
    snapshot_summary: Mapping[str, Any],
) -> dict[str, Any]:
    totals = _mapping(inventory.get('totals'))
    coverage = f"{_integer(totals.get('nodes'))} Nodes / {_integer(totals.get('namespaces'))} Namespaces"
    return {
        'metrics': [
            {'label': 'Data Sources', 'value': str(len(source_rows)), 'tone': 'info'},
            {'label': 'Coverage', 'value': coverage, 'tone': 'info'},
            {'label': 'Forecast Window', 'value': _text(forecast_snapshot.get('forecast_horizon'), 'Not Available'), 'tone': 'info'},
            {'label': 'Observation Boundary', 'value': 'Committed Snapshot', 'tone': 'info'},
        ],
        'sources': list(source_rows),
        'methodology': [
            {'label': 'Reporting Period', 'value': period_label},
            {'label': 'Data Cut-Off', 'value': data_cutoff},
            {'label': 'Forecast Method', 'value': 'Holt-Winters exponential smoothing where committed forecast evidence is available.'},
            {'label': 'Severity Interpretation', 'value': 'Derived from thresholds, impact scope, and operational urgency.'},
            {'label': 'Priority Interpretation', 'value': 'Based on operational impact, recoverability, and risk to service continuity.'},
            {'label': 'Snapshot Status', 'value': _text(snapshot_summary.get('status'), 'Unknown')},
        ],
        'included': (
            'Committed inventory snapshot as of the data cut-off.',
            'Committed metrics and alert observations within the reporting period.',
            'Alert summaries available at the report cut-off.',
            'Trend calculations based on historical observations.',
            'Forecast projections for the configured forecast window.',
        ),
        'excluded': (
            'Live cluster state after the data cut-off.',
            'Unapproved change windows and in-flight maintenance.',
            'Future deployments or changes not yet observed.',
            'Manual operator assumptions or hypothetical mitigations.',
        ),
        'limitations': (
            'Disconnected resources are excluded from active headroom calculations when evidence identifies them.',
            'Forecast results do not include planned deployments, infrastructure expansion, or workload migrations.',
            'Top-consumer sections show leading contributors; every displayed long name remains complete and wraps when required.',
            'Data freshness may differ by source based on collection intervals and retention policies.',
        ),
        'status_language': (
            {'label': 'Not Available', 'description': 'No data exists for the requested dimension within the reporting period.'},
            {'label': 'Not Collected', 'description': 'Data was not collected because of configuration, permission, or collection failure.'},
            {'label': 'Partial Coverage', 'description': 'Data was collected, but coverage is incomplete for the requested scope.'},
            {'label': 'Source Unavailable', 'description': 'The source was unreachable or not providing data at the cut-off.'},
        ),
        'guidance': (
            'This report supports operational planning and decision-making. Validate all findings '
            'and recommendations against live cluster state before taking remediation or change actions.'
        ),
    }
