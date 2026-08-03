from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
import re
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
        'presentation_version': 'v2.9-methodology-table-redesign',
        'layout_contract': {
            'paper': 'A4 Portrait',
            'section_page_breaks': True,
            'truncate_identities': True,
            'identity_policy': 'top-n-summarized',
            'status_style': 'plain-colored-text',
            'visual_style': 'reporting-standard-v2.9-analytics-family',
        },
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

    resource_metrics = _resource_metrics(
        resource_snapshot,
        evidence_state=_metric_evidence_state(payload, snapshot_summary),
    )
    forecast_series = _forecast_series(forecast_snapshot)
    resource_metrics = _reconcile_resource_metrics(
        resource_metrics,
        forecast_series=forecast_series,
        storage_snapshot=storage_snapshot,
        capacity_snapshot=capacity_snapshot,
        inventory_snapshot=inventory_snapshot,
    )
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
        'management_summary': _management_summary(
            resource_metrics=resource_metrics,
            storage_snapshot=storage_snapshot,
            inventory=inventory,
            alerts_snapshot=alerts_snapshot,
            forecast_snapshot=forecast_snapshot,
            priority_findings=priority_findings,
        ),
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
    for group in consumer_groups.values():
        _normalize_consumer_bars(group)
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

    alert_metrics = _alert_metrics(alerts_snapshot, alert_detail)
    alert_category_mix = _alert_category_mix(alert_items)
    alerts_page = {
        'metrics': alert_metrics,
        'profile': _alert_profile(alert_metrics, alert_category_mix),
        'severity_svg': _alert_severity_svg(alerts_snapshot, alert_detail),
        'category_mix': alert_category_mix,
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


def _percent(card: Mapping[str, Any]) -> float | None:
    for key in (
        'percent',
        'value',
        'usage_percent',
        'utilization_percent',
        'current_percent',
        'p95_percent',
        'current',
        'p95',
    ):
        raw = card.get(key)
        if isinstance(raw, Mapping):
            raw = raw.get('percent') or raw.get('value') or raw.get('current')
        if raw is not None and str(raw).strip() != '':
            return max(0.0, min(_number(raw), 100.0))
    for key in ('metric', 'usage', 'utilization', 'current_value'):
        nested = _mapping(card.get(key))
        if nested:
            value = _percent(nested)
            if value is not None:
                return value
    return None


def _display_percent(value: float | None) -> str:
    if value is None:
        return 'Not Available'
    return f'{value:.1f}%'


def _metric_tone(percent: float | None) -> str:
    if percent is None:
        return 'neutral'
    if percent >= 85.0:
        return 'critical'
    if percent >= 70.0:
        return 'warning'
    return 'normal'


def _set_metric_percent(
    metric: Mapping[str, Any],
    percent: float | None,
    *,
    source_note: str,
) -> dict[str, Any]:
    result = dict(metric)
    if percent is None:
        return result
    percent = max(0.0, min(float(percent), 100.0))
    tone = _metric_tone(percent)
    result.update(
        {
            'value': _display_percent(percent),
            'percent': percent,
            'chart_percent': percent,
            'headroom_percent': max(0.0, 100.0 - percent),
            'available': True,
            'status': 'Critical' if tone == 'critical' else 'Warning' if tone == 'warning' else 'Normal',
            'tone': tone,
            'description': source_note,
        }
    )
    return result


def _nested_number(source: Mapping[str, Any], *paths: tuple[str, ...]) -> float | None:
    for path in paths:
        value: Any = source
        for key in path:
            if not isinstance(value, Mapping):
                value = None
                break
            value = value.get(key)
        if value is None or str(value).strip() == '':
            continue
        if isinstance(value, Mapping):
            value = value.get('percent') or value.get('value') or value.get('current')
        if value is None or str(value).strip() == '':
            continue
        return _number(value)
    return None


def _reconcile_resource_metrics(
    metrics: Mapping[str, Mapping[str, Any]],
    *,
    forecast_series: Sequence[Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    capacity_snapshot: Mapping[str, Any],
    inventory_snapshot: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Reconcile overview metrics against committed evidence without inventing values.

    Some collectors expose aggregate metrics in different payload branches. The
    report uses the primary resource snapshot first, then an explicit committed
    fallback. A positive committed fallback replaces a missing or zero primary
    value only when the sources would otherwise contradict each other.
    """
    result = {key: dict(value) for key, value in metrics.items()}
    series_map = {str(item.get('key') or '').lower(): item for item in forecast_series}

    for key in ('cpu', 'memory'):
        metric = result.get(key, {})
        current = metric.get('percent') if metric.get('available') else None
        latest = _number(_mapping(series_map.get(key)).get('latest_percent'), -1.0)
        if latest >= 0.0 and (current is None or (current <= 0.0 and latest >= 0.5)):
            result[key] = _set_metric_percent(
                metric,
                latest,
                source_note=f"{_text(metric.get('label'), key.title())} utilization from the latest committed observation.",
            )

    storage_used = _nested_number(
        storage_snapshot,
        ('used_percent',),
        ('utilization_percent',),
        ('usage_percent',),
    )
    if storage_used is None and storage_snapshot.get('free_percent') is not None:
        storage_used = max(0.0, 100.0 - _number(storage_snapshot.get('free_percent')))
    storage_metric = result.get('storage', {})
    storage_current = storage_metric.get('percent') if storage_metric.get('available') else None
    if storage_used is not None and (storage_current is None or (storage_current <= 0.0 and storage_used >= 0.5)):
        result['storage'] = _set_metric_percent(
            storage_metric,
            storage_used,
            source_note='Storage utilization derived from committed requested and free-capacity evidence.',
        )

    pods_percent = _nested_number(
        capacity_snapshot,
        ('pod_utilization_percent',),
        ('pods_percent',),
        ('pod_usage_percent',),
        ('pods', 'percent'),
        ('pod_capacity', 'used_percent'),
    )
    if pods_percent is None:
        remaining = _nested_number(
            capacity_snapshot,
            ('pod_capacity_remaining',),
            ('pods_remaining',),
            ('pod_capacity', 'remaining'),
        )
        used = _nested_number(inventory_snapshot, ('total_pods',))
        if used is not None and remaining is not None and used + remaining > 0:
            pods_percent = used / (used + remaining) * 100.0
    pods_metric = result.get('pods', {})
    pods_current = pods_metric.get('percent') if pods_metric.get('available') else None
    if pods_percent is not None and (pods_current is None or (pods_current <= 0.0 and pods_percent >= 0.5)):
        result['pods'] = _set_metric_percent(
            pods_metric,
            pods_percent,
            source_note='Pod utilization derived from committed pod inventory and remaining scheduling capacity.',
        )
    return result


def _unavailable_state(value: Any) -> bool:
    normalized = _status(value, '').strip().lower()
    return any(
        token in normalized
        for token in (
            'not available',
            'unavailable',
            'not collected',
            'failed',
            'degraded',
            'error',
            'insufficient',
            'unknown',
        )
    )


def _metric_evidence_state(
    payload: Mapping[str, Any],
    snapshot_summary: Mapping[str, Any],
) -> dict[str, Any]:
    prometheus = _mapping(payload.get('prometheus'))
    candidates = (
        prometheus.get('status_label'),
        prometheus.get('status'),
        snapshot_summary.get('status'),
    )
    first_problem = next((value for value in candidates if _unavailable_state(value)), None)
    if first_problem is not None:
        return {
            'available': False,
            'status': _status(first_problem, 'Source Unavailable'),
            'tone': _tone(first_problem),
        }
    return {'available': True, 'status': 'Current', 'tone': 'normal'}


def _resource_metrics(
    resource_snapshot: Mapping[str, Any],
    *,
    evidence_state: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    evidence_state = _mapping(evidence_state)
    evidence_available = evidence_state.get('available') is not False
    for key, label in (
        ('cpu', 'CPU'),
        ('memory', 'Memory'),
        ('storage', 'Storage'),
        ('pods', 'Pods'),
    ):
        card = _mapping(resource_snapshot.get(key))
        percent = _percent(card)
        card_status = _status(card.get('status'), '')
        available = bool(card) and percent is not None and evidence_available and not _unavailable_state(card_status)
        if available:
            tone = _tone(card.get('tone') or card.get('status'))
            status = card_status or 'Current'
            description = _text(card.get('description'), f'{label} utilization at the report cut-off.')
            headroom = max(0.0, 100.0 - percent)
        else:
            percent = None
            headroom = None
            status = _status(evidence_state.get('status'), card_status or 'Not Available')
            tone = _tone(evidence_state.get('tone') or status)
            description = (
                f'{label} utilization is not available because the committed metric evidence is {status.lower()}.'
            )
        result[key] = {
            'key': key,
            'label': label,
            'value': _display_percent(percent),
            'percent': percent,
            'chart_percent': percent if percent is not None else 0.0,
            'headroom_percent': headroom,
            'available': available,
            'status': status,
            'tone': tone,
            'description': description,
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
    free = None
    if storage.get('free_percent') is not None:
        free = max(0.0, min(_number(storage.get('free_percent')), 100.0))
    elif storage.get('used_percent') is not None:
        free = max(0.0, 100.0 - _number(storage.get('used_percent')))
    risks = _integer(storage.get('pvc_risk_count'))
    if free is None:
        tone = 'warning' if risks else 'neutral'
        status = 'Review' if risks else 'Not Available'
    else:
        tone = 'critical' if free < 10 else 'warning' if risks or free < 30 else 'normal'
        status = 'Critical' if tone == 'critical' else 'Review' if tone == 'warning' else 'Normal'
    return {
        'label': 'Storage Headroom',
        'value': _display_percent(free),
        'status': status,
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
                'summary': _text(recommendation.get('summary') or recommendation.get('description'), ''),
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


def _management_decision_summary(item: Mapping[str, Any], title: str, description: str) -> str:
    explicit = item.get('management_decision') or item.get('summary') or item.get('decision')
    if explicit:
        return _text(explicit)
    text = description.strip()
    # Technical identifiers belong in the evidence pages, not in the executive table.
    for marker in (' Namespace:', ' namespace:', ' Pod:', ' pod:', ' Resource:', ' resource:', ' Value:', ' value:'):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip(' .') + '.'
            break
    if len(text) > 180:
        text = text[:177].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'
    return text or f'Review {title.lower()} and confirm the accountable owner.'



def _register_title(title: str) -> str:
    """Return a concise table label while preserving the full title in reference notes."""
    value = _text(title, 'Recommendation')
    for prefix in ('Review ', 'Validate ', 'Investigate ', 'Assess '):
        if value.lower().startswith(prefix.lower()):
            value = value[len(prefix):].strip()
            break
    if len(value) > 48:
        value = value[:45].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'
    return value or _text(title, 'Recommendation')

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
            item.get('description') or item.get('reason') or item.get('evidence'),
            'Review the related evidence and confirm the appropriate operational action.',
        )
        recommended_action = _text(
            item.get('recommended_action') or item.get('action') or item.get('remediation'),
            description,
        )
        management_summary = _management_decision_summary(item, title, description)
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
                'register_title': _register_title(title),
                'description': description,
                'summary': management_summary,
                'recommended_action': recommended_action,
                'scope': scope,
                'source': source,
                'owner': _text(item.get('owner'), _suggest_owner(source, title)),
                'target': _text(item.get('target') or item.get('due'), _target_window(tone)),
                'status': _text(item.get('status'), 'Open' if tone in {'critical', 'warning'} else 'Planned'),
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
            'description': _text(item.get('summary') or item.get('description'), ''),
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


def _management_summary(
    *,
    resource_metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
    alerts_snapshot: Mapping[str, Any],
    forecast_snapshot: Mapping[str, Any],
    priority_findings: Sequence[Mapping[str, Any]],
) -> str:
    """Build a compact, management-oriented narrative for the overview page.

    The narrative deliberately summarizes the committed evidence instead of
    repeating the full detail register. Missing metrics are described as
    unavailable rather than silently converted to zero.
    """
    available = [
        item
        for item in resource_metrics.values()
        if _mapping(item).get('available') and _mapping(item).get('percent') is not None
    ]
    if available:
        highest = max(available, key=lambda item: _number(item.get('percent')))
        highest_percent = _number(highest.get('percent'))
        if highest_percent < 0.5:
            resource_sentence = (
                'Shared-resource utilization is below 0.5% in the current committed snapshot; '
                'validate source recency before treating the value as an operating baseline.'
            )
        else:
            resource_sentence = (
                f"{_text(highest.get('label'))} is the highest available shared-resource signal "
                f"at {_display_percent(highest_percent)}."
            )
    else:
        resource_sentence = (
            'Shared CPU and memory utilization are not available from the committed metric evidence.'
        )

    concerns: list[str] = []
    not_ready = _integer(inventory.get('not_ready_nodes'))
    if not_ready:
        concerns.append(f'{not_ready} not-ready node(s)')
    storage_risks = _integer(storage_snapshot.get('pvc_risk_count'))
    if storage_risks:
        concerns.append(f'{storage_risks} local storage risk item(s)')
    critical_alerts = _integer(alerts_snapshot.get('critical'))
    warning_alerts = _integer(alerts_snapshot.get('warning'))
    if critical_alerts or warning_alerts:
        concerns.append(f'{critical_alerts} critical and {warning_alerts} warning alert(s)')

    if concerns:
        concern_sentence = 'The main review areas are ' + ', '.join(concerns) + '.'
    elif priority_findings:
        concern_sentence = 'The current overview contains findings that require operational follow-up.'
    else:
        concern_sentence = 'No immediate operational risk was identified in the committed overview evidence.'

    forecast_note = _text(forecast_snapshot.get('risk_note'), '')
    if forecast_note:
        forecast_sentence = forecast_note.rstrip('.') + '.'
    else:
        forecast_sentence = 'Forecast conclusions remain limited to the committed historical observation window.'

    return f'{resource_sentence} {concern_sentence} {forecast_sentence}'


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
    current = metric.get('percent') if metric.get('available') else None
    return {
        **metric,
        'current': _display_percent(current),
        'p95': _display_percent(current),
        'headroom': _display_percent(max(0.0, 100.0 - current) if current is not None else None),
        'chart_percent': current if current is not None else 0.0,
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
    pods_used_count = _integer(_mapping(inventory.get('totals')).get('pods'))
    pods_remaining = _nested_number(
        capacity_snapshot,
        ('pod_capacity_remaining',),
        ('pods_remaining',),
        ('pod_capacity', 'remaining'),
    )
    pods_total = pods_used_count + int(round(pods_remaining or 0)) if pods_used_count and pods_remaining is not None else 0
    pods_capacity_label = f'{pods_total} Total' if pods_total else _text(_mapping(capacity_snapshot.get('pod_capacity_remaining')).get('value'), 'Not Available')
    pods_headroom_label = (
        f'{int(round(pods_remaining))} Remaining ({_display_percent(pods_metric.get("headroom_percent"))})'
        if pods_remaining is not None
        else _display_percent(pods_metric.get('headroom_percent'))
    )
    storage_risks = _integer(storage_snapshot.get('pvc_risk_count'))
    storage_tone = _tone(storage_snapshot.get('tone'))
    if storage_tone == 'neutral':
        storage_tone = 'warning' if storage_risks or storage_free < 30.0 else 'normal'
    storage_status = _status(storage_snapshot.get('status'), '')
    if not storage_status:
        storage_status = 'Review' if storage_tone == 'warning' else 'Critical' if storage_tone == 'critical' else 'Normal'
    storage_used_percent = max(0.0, min(100.0, 100.0 - storage_free))
    return [
        {
            'resource': 'Storage',
            'used': _text(storage_snapshot.get('pvc_used'), 'Not Available'),
            'capacity': _text(storage_snapshot.get('pvc_requested'), 'Not Available'),
            'headroom': _display_percent(storage_free),
            'chart_percent': storage_used_percent,
            'chart_value': f'{_display_percent(storage_used_percent)} used',
            'chart_headroom': f'{_display_percent(storage_free)} headroom',
            'interpretation': (
                f'{storage_risks} local volume risk item(s) detected.'
                if storage_risks
                else 'No local persistent volume risk item detected.'
            ),
            'status': storage_status,
            'tone': storage_tone,
        },
        {
            'resource': 'Pods',
            'used': _text(pods_metric.get('value')),
            'capacity': pods_capacity_label,
            'headroom': pods_headroom_label,
            'chart_percent': _number(pods_metric.get('percent')),
            'chart_value': f"{_text(pods_metric.get('value'))} used",
            'chart_headroom': f"{_display_percent(pods_metric.get('headroom_percent'))} headroom",
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
    available_metrics = [item for item in resource_metrics.values() if item.get('available')]
    highest = max(available_metrics, key=lambda item: _number(item.get('percent')), default={})
    pvc_risks = _integer(storage_snapshot.get('pvc_risk_count'))
    not_ready = _integer(inventory.get('not_ready_nodes'))
    if highest:
        highest_label = _text(highest.get('label'), 'Resource')
        highest_percent = _number(highest.get('percent'))
        if highest_percent < 0.5:
            details = ['Shared-resource utilization is below 0.5%; source recency should be validated before operational use.']
        else:
            details = [f'{highest_label} is the highest available shared resource signal at {_display_percent(highest_percent)}.']
    else:
        details = ['Shared CPU and memory signals are not available from the committed metric evidence.']
    if pvc_risks:
        details.append(f'{pvc_risks} local storage item(s) require separate review.')
    if not_ready:
        details.append(f'{not_ready} node(s) are not ready and are excluded from active capacity assumptions.')
    return ' '.join(details)


def _forecast_series(forecast_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_series = _sequence(forecast_snapshot.get('series'))
    if not raw_series:
        return []

    # Preferred payload: one record per resource with precomputed chart points.
    if any(isinstance(item, Mapping) and item.get('key') for item in raw_series):
        result: list[dict[str, Any]] = []
        for item in raw_series:
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

    # Compatibility payload: a flat historical/forecast series, currently used
    # for memory demand. Convert it into the canonical resource record.
    points = [item for item in raw_series if isinstance(item, Mapping)]
    if not points:
        return []
    historical_values = [_number(item.get('value')) for item in points if str(item.get('kind') or '').lower() == 'historical']
    forecast_values = [_number(item.get('value')) for item in points if str(item.get('kind') or '').lower() == 'forecast']
    all_values = historical_values + forecast_values
    if not all_values:
        return []

    def chart_points(values: Sequence[float], start: float, end: float) -> str:
        if not values:
            return ''
        if len(values) == 1:
            xs = [start]
        else:
            step = (end - start) / (len(values) - 1)
            xs = [start + index * step for index in range(len(values))]
        return ' '.join(f'{x:.2f},{100.0 - max(0.0, min(value, 100.0)):.2f}' for x, value in zip(xs, values, strict=False))

    historical_points = chart_points(historical_values, 0.0, 54.0)
    forecast_points = chart_points(forecast_values, 54.0, 100.0)
    latest = historical_values[-1] if historical_values else all_values[0]
    projected = forecast_values[-1] if forecast_values else latest
    return [
        {
            'key': 'memory',
            'label': 'Memory',
            'historical_points': historical_points,
            'forecast_points': forecast_points,
            'latest_percent': latest,
            'projected_percent': projected,
            'trend': 'Increasing' if projected > latest else 'Stable',
        }
    ]


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

    label = escape(_text(selected.get('label'), 'Resource'))
    historical = _scaled_chart_points(_text(selected.get('historical_points'), ''))
    forecast = _scaled_chart_points(_text(selected.get('forecast_points'), ''))
    projected = max(0.0, min(_number(selected.get('projected_percent')), 100.0))
    latest = max(0.0, min(_number(selected.get('latest_percent')), 100.0))
    forecast_start_x = 430.0
    if forecast:
        try:
            forecast_start_x = float(forecast.split()[0].split(',')[0])
        except (IndexError, TypeError, ValueError):
            forecast_start_x = 430.0

    historical_line = (
        f'<polyline points="{escape(historical)}" fill="none" stroke="#7c3aed" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        if historical else ''
    )
    forecast_line = (
        f'<polyline points="{escape(forecast)}" fill="none" stroke="#8b5cf6" '
        'stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" stroke-linejoin="round"/>'
        if forecast else ''
    )
    projected_y = _chart_y(projected)
    latest_y = _chart_y(latest)
    # Keep the terminal value label away from the warning/critical threshold labels.
    if 66.0 <= projected <= 74.0 or 81.0 <= projected <= 89.0:
        projected_label_y = min(178.0, projected_y + 16.0)
    else:
        projected_label_y = max(14.0, projected_y - 9.0)
    threshold_label_x = min(610.0, forecast_start_x + 165.0)

    return f'''<svg class="ao-chart-svg chart" viewBox="0 0 800 230" role="img" aria-label="{label} demand forecast">
        <rect x="{forecast_start_x:.1f}" y="18" width="{748-forecast_start_x:.1f}" height="164" fill="#faf7ff"/>
        <text x="{forecast_start_x + 12:.1f}" y="32" fill="#6d28d9" font-size="10" font-weight="700">FORECAST</text>
        <g stroke="#e5e7eb" stroke-width="1">
            <line x1="68" x2="748" y1="182" y2="182"/><line x1="68" x2="748" y1="143" y2="143"/>
            <line x1="68" x2="748" y1="104" y2="104"/><line x1="68" x2="748" y1="65" y2="65"/>
            <line x1="68" x2="748" y1="39" y2="39"/>
        </g>
        <line x1="68" x2="748" y1="65" y2="65" stroke="#d97706" stroke-width="1.3" stroke-dasharray="6 5"/>
        <line x1="68" x2="748" y1="39" y2="39" stroke="#dc2626" stroke-width="1.3" stroke-dasharray="6 5"/>
        <line x1="{forecast_start_x:.1f}" x2="{forecast_start_x:.1f}" y1="18" y2="182" stroke="#a78bfa" stroke-width="1.1" stroke-dasharray="4 4"/>
        <g fill="#64748b" font-size="10"><text x="24" y="186">0%</text><text x="24" y="147">25%</text>
            <text x="24" y="108">50%</text><text x="24" y="69">70%</text><text x="24" y="43">85%</text></g>
        <text x="{threshold_label_x:.1f}" y="60" text-anchor="start" fill="#b45309" font-size="9.5">Warning 70%</text>
        <text x="{threshold_label_x:.1f}" y="34" text-anchor="start" fill="#b91c1c" font-size="9.5">Critical 85%</text>
        {historical_line}{forecast_line}
        <circle cx="{forecast_start_x:.1f}" cy="{latest_y:.1f}" r="3.4" fill="#7c3aed"/>
        <circle cx="742" cy="{projected_y:.1f}" r="3.6" fill="#8b5cf6"/>
        <text x="730" y="{projected_label_y:.1f}" text-anchor="end" fill="#5b21b6" font-size="10.5" font-weight="700">{projected:.1f}%</text>
        <g fill="#64748b" font-size="9.2" text-anchor="middle"><text x="68" y="207">Start</text>
            <text x="284" y="207">Historical</text><text x="536" y="207">Near-term</text><text x="742" y="207">Horizon</text></g>
        <line x1="80" x2="108" y1="223" y2="223" stroke="#7c3aed" stroke-width="2.5"/>
        <text x="114" y="227" fill="#64748b" font-size="8.8">Historical P95</text>
        <line x1="238" x2="266" y1="223" y2="223" stroke="#8b5cf6" stroke-width="2.5" stroke-dasharray="7 5"/>
        <text x="272" y="227" fill="#64748b" font-size="8.8">Projected demand</text>
        <line x1="420" x2="448" y1="223" y2="223" stroke="#d97706" stroke-width="1.4" stroke-dasharray="6 5"/>
        <text x="454" y="227" fill="#64748b" font-size="8.8">Threshold</text>
    </svg>'''


def _scaled_chart_points(points: str) -> str:
    if not points:
        return ''
    scaled: list[str] = []
    for token in points.split():
        try:
            raw_x, raw_y = token.split(',', 1)
            x = 68.0 + (float(raw_x) / 100.0) * 674.0
            y = 18.0 + (float(raw_y) / 100.0) * 164.0
        except (TypeError, ValueError):
            continue
        scaled.append(f'{x:.2f},{y:.2f}')
    return ' '.join(scaled)


def _chart_y(percent: float) -> float:
    return 182.0 - (max(0.0, min(percent, 100.0)) / 100.0) * 164.0


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
        metric = _mapping(resource_metrics.get(key))
        current = metric.get('percent') if metric.get('available') else None
        item = _mapping(item_map.get(key))
        projected = _number(item.get('projected_percent'), current or 0.0) if item else None
        trend = _text(item.get('trend'), _text(forecast_snapshot.get(f'{key}_trend'), 'Unknown'))
        eta = nearest_label if key == nearest_resource else 'Not projected'
        confidence = 'High' if item else 'Not Available'
        tone = 'neutral' if projected is None else 'critical' if projected >= 85 else 'warning' if projected >= 70 else 'normal'
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
                    if projected is not None and tone == 'critical'
                    else 'Projected to enter or remain in the warning band.'
                    if projected is not None and tone == 'warning'
                    else 'Not available from the committed forecast evidence.' if projected is None else 'Stable within the current operating window.'
                ),
            }
        )
    return rows


def _forecast_interpretation(forecast_snapshot: Mapping[str, Any]) -> str:
    return _text(
        forecast_snapshot.get('risk_note'),
        'Forecast evidence is unavailable or does not currently indicate a threshold breach.',
    )


def _measurement_number(value: Any) -> float:
    text = str(value or '')
    match = re.search(r'-?\d+(?:[.,]\d+)?', text)
    if not match:
        return 0.0
    return _number(match.group(0).replace(',', '.'))


def _consumer_rows(items: Sequence[Any], resource_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items[:8], start=1):
        if not isinstance(item, Mapping):
            continue
        name = _text(item.get('name') or item.get('workload') or item.get('pod'), 'Unnamed Resource')
        namespace = _text(item.get('namespace'), 'Cluster Scoped')
        display = _text(item.get('display_value') or item.get('value'), 'Not Available')
        share_percent = None
        if item.get('percent') is not None:
            share_percent = max(0.0, min(_number(item.get('percent')), 100.0))
        raw_value = _measurement_number(display)
        rows.append(
            {
                'rank': index,
                'marker': str(index),
                'name': name,
                'namespace': namespace,
                'resource': resource_label,
                'value': display,
                'raw_value': raw_value,
                'percent': share_percent if share_percent is not None else 0.0,
                'bar_percent': 0.0,
                'status': 'Review' if share_percent is not None and share_percent >= 10 else 'Observed',
                'tone': 'warning' if share_percent is not None and share_percent >= 10 else 'info',
            }
        )
    return rows


def _normalize_consumer_bars(rows: Sequence[dict[str, Any]]) -> None:
    maximum = max((_number(item.get('raw_value')) for item in rows), default=0.0)
    if maximum <= 0:
        maximum = max((_number(item.get('percent')) for item in rows), default=0.0)
        source_key = 'percent'
    else:
        source_key = 'raw_value'
    for item in rows:
        value = _number(item.get(source_key))
        item['bar_percent'] = max(4.0 if value > 0 else 0.0, min(100.0, value / maximum * 100.0 if maximum else 0.0))


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
        available = bool(metric.get('available'))
        percent = metric.get('percent') if available else None
        headroom = _display_percent(max(0.0, 100.0 - percent) if percent is not None else None)
        if key == 'storage' and storage_snapshot.get('free_percent') is not None:
            headroom = _display_percent(_number(storage_snapshot.get('free_percent')))
        rows.append(
            {
                'resource': label,
                'used': _display_percent(percent),
                'capacity': '100% reference' if available else 'Not Available',
                'headroom': headroom,
                'percent': percent if percent is not None else 0.0,
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
        (item for item in resource_metrics.values() if item.get('available') and item.get('percent') is not None),
        key=lambda item: _number(item.get('percent')),
        reverse=True,
    )[:2]
    if constrained and _number(constrained[0].get('percent')) >= 0.5:
        names = ' and '.join(_text(item.get('label')) for item in constrained)
        base = f'{names} are the most constrained shared resources in the current committed snapshot.'
    elif constrained:
        base = 'Shared-resource utilization is below 0.5%; verify the current metric collection window before remediation.'
    else:
        base = 'Shared-resource utilization is not available from the committed metric evidence.'
    not_ready = _integer(inventory.get('not_ready_nodes'))
    suffix = f' {not_ready} node(s) are not ready.' if not_ready else ''
    return base + suffix


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

    def first_integer(*values: Any) -> int:
        for value in values:
            if value is not None and value != '':
                return _integer(value)
        return 0

    critical = first_integer(
        summary.get('critical'),
        summary.get('critical_alerts'),
        alerts_snapshot.get('critical_alerts'),
        alerts_snapshot.get('critical'),
    )
    warning = first_integer(
        summary.get('warning'),
        summary.get('warning_alerts'),
        alerts_snapshot.get('warning_alerts'),
        alerts_snapshot.get('warning'),
    )
    info = first_integer(summary.get('info'), summary.get('info_alerts'), alerts_snapshot.get('info'))
    anomalies = first_integer(
        summary.get('anomalies'),
        alerts_snapshot.get('recent_anomalies'),
        alerts_snapshot.get('anomalies'),
    )
    return [
        {'label': 'Critical Alerts', 'value': str(critical), 'status': 'Requires Immediate Action' if critical else 'Clear', 'tone': 'critical' if critical else 'normal'},
        {'label': 'Warning Alerts', 'value': str(warning), 'status': 'Requires Attention' if warning else 'Clear', 'tone': 'warning' if warning else 'normal'},
        {'label': 'Info Alerts', 'value': str(info), 'status': 'Informational', 'tone': 'info'},
        {'label': 'Anomalies Detected', 'value': str(anomalies), 'status': 'Unusual Patterns' if anomalies else 'None Detected', 'tone': 'info' if anomalies else 'normal'},
    ]


def _alert_profile(
    metrics: Sequence[Mapping[str, Any]],
    category_mix: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    severity_rows: list[dict[str, Any]] = []
    tones = ('critical', 'warning', 'info')
    values = [max(0, _integer(metric.get('value'))) for metric in metrics[:3]]
    active_total = sum(values)

    for metric, tone, value in zip(metrics[:3], tones, values):
        label = _text(metric.get('label'), 'Alert').removesuffix(' Alerts')
        severity_rows.append(
            {
                'label': label,
                'value': value,
                'percent': (value / active_total * 100) if active_total else 0,
                'tone': tone,
            }
        )

    critical, warning, info = values
    if critical:
        status = 'Requires Immediate Action'
        tone = 'critical'
    elif warning:
        status = 'Requires Attention'
        tone = 'warning'
    elif info:
        status = 'Informational'
        tone = 'info'
    else:
        status = 'Clear'
        tone = 'normal'

    categorized_total = sum(max(0, _integer(item.get('value'))) for item in category_mix)
    category_coverage_label = (
        f'{categorized_total} / {active_total} categorized' if active_total else 'No active alerts'
    )
    return {
        'active_total': active_total,
        'status': status,
        'tone': tone,
        'severity': severity_rows,
        'categorized_total': categorized_total,
        'category_coverage_label': category_coverage_label,
    }


def _alert_severity_svg(alerts_snapshot: Mapping[str, Any], alert_detail: Mapping[str, Any]) -> str:
    """Render an executive donut chart for critical, warning, and info alerts.

    The chart keeps the distribution readable when one severity dominates and
    still shows a neutral ring when no active alert is present.
    """
    metrics = _alert_metrics(alerts_snapshot, alert_detail)
    labels = ('Critical', 'Warning', 'Info')
    colors = ('#DC2626', '#D97706', '#2563EB')
    values = [max(0.0, _number(metric['value'])) for metric in metrics[:3]]
    total = sum(values)

    radius = 46.0
    circumference = 2 * 3.141592653589793 * radius
    cumulative = 0.0
    segments: list[str] = []
    if total > 0:
        for value, color in zip(values, colors):
            if value <= 0:
                continue
            length = circumference * (value / total)
            offset = -circumference * (cumulative / total)
            segments.append(
                '<circle cx="108" cy="76" r="46" fill="none" '
                f'stroke="{color}" stroke-width="18" stroke-linecap="butt" '
                f'stroke-dasharray="{length:.3f} {circumference - length:.3f}" '
                f'stroke-dashoffset="{offset:.3f}" transform="rotate(-90 108 76)"/>'
            )
            cumulative += value

    legend = []
    for index, (label, value, color) in enumerate(zip(labels, values, colors)):
        y = 42 + index * 29
        legend.append(
            f'<rect x="204" y="{y - 8}" width="10" height="10" rx="2" fill="{color}"/>'
            f'<text x="224" y="{y}" class="donut-legend-label">{label}</text>'
            f'<text x="330" y="{y}" text-anchor="end" class="donut-legend-value">{int(value)}</text>'
        )

    centre_line_1 = 'Active' if total else 'No Active'
    centre_line_2 = 'Alerts'
    return (
        '<svg class="ao-chart-svg ao-alert-donut" viewBox="0 0 350 155" role="img" '
        'aria-label="Alert severity distribution">'
        '<circle cx="108" cy="76" r="46" fill="none" stroke="#E5E7EB" stroke-width="18"/>'
        + ''.join(segments)
        + f'<text x="108" y="67" text-anchor="middle" class="donut-total">{int(total)}</text>'
        + f'<text x="108" y="86" text-anchor="middle" class="donut-caption">{centre_line_1}</text>'
        + f'<text x="108" y="98" text-anchor="middle" class="donut-caption">{centre_line_2}</text>'
        + ''.join(legend)
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


def _report_activity(reports: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = {'Ready': 0, 'Generating': 0, 'Failed': 0, 'Other': 0}
    tones = {'Ready': 'normal', 'Generating': 'info', 'Failed': 'critical', 'Other': 'neutral'}
    for report in reports:
        status = _text(report.get('status'), 'Other').lower()
        if 'ready' in status or 'complete' in status or 'available' in status:
            counts['Ready'] += 1
        elif 'generat' in status or 'running' in status or 'pending' in status:
            counts['Generating'] += 1
        elif 'fail' in status or 'error' in status:
            counts['Failed'] += 1
        else:
            counts['Other'] += 1
    maximum = max(counts.values(), default=0) or 1
    return [
        {
            'label': label,
            'value': value,
            'percent': value / maximum * 100.0,
            'tone': tones[label],
        }
        for label, value in counts.items()
        if value or label in {'Ready', 'Generating', 'Failed'}
    ]


def _title_like(value: str) -> str:
    text = _text(value)
    if not text:
        return text
    specials = {'s3': 'S3', 'cpu': 'CPU', 'p95': 'P95', 'api': 'API', 'utc': 'UTC'}
    words = []
    for word in text.split():
        key = word.lower()
        words.append(specials.get(key, word if any(ch.isupper() for ch in word[1:]) else word.capitalize()))
    return ' '.join(words)


def _reporting(reporting_summary: Mapping[str, Any]) -> dict[str, Any]:
    counts = _mapping(reporting_summary.get('counts'))
    recent = _sequence(reporting_summary.get('recent_reports'))
    schedules = _sequence(reporting_summary.get('schedules'))
    storage = _mapping(reporting_summary.get('storage'))
    generated = _integer(counts.get('generated_this_month') or counts.get('total'))
    normalized_recent = [_normalize_recent_report(item) for item in recent[:6]]
    activity = _report_activity(normalized_recent)
    metrics = [
        {'label': 'Reports Generated', 'value': str(generated), 'note': 'Current reporting period', 'tone': 'info'},
        {'label': 'Scheduled Reports', 'value': str(_integer(counts.get('active_schedules'))), 'note': 'Active schedules', 'tone': 'normal'},
        {'label': 'Ready Reports', 'value': str(_integer(counts.get('ready'))), 'note': 'Available for download', 'tone': 'info'},
        {'label': 'Failed Reports', 'value': str(_integer(counts.get('failed'))), 'note': 'Requires review', 'tone': 'critical' if _integer(counts.get('failed')) else 'normal'},
    ]
    return {
        'metrics': metrics,
        'recent_reports': normalized_recent,
        'activity': activity,
        'schedules': [_normalize_schedule(item) for item in schedules[:6]],
        'storage': {
            'backend': _title_like(_text(storage.get('backend'), 'Not Available')),
            'status': _title_like(_text(storage.get('status'), 'Not Available')),
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
                'ready_nodes': _integer(counts.get('ready_nodes') or item.get('ready_nodes')),
                'not_ready_nodes': _integer(counts.get('not_ready_nodes') or item.get('not_ready_nodes')),
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
    explicit_not_ready = next(
        (
            _integer(value)
            for value in (
                inventory_snapshot.get('not_ready_nodes'),
                inventory_snapshot.get('nodes_not_ready'),
                health.get('not_ready_nodes'),
                health.get('nodes_not_ready'),
            )
            if value is not None and str(value).strip() != ''
        ),
        None,
    )
    explicit_ready = next(
        (
            _integer(value)
            for value in (
                inventory_snapshot.get('ready_nodes'),
                inventory_snapshot.get('nodes_ready'),
                health.get('ready_nodes'),
                health.get('nodes_ready'),
            )
            if value is not None and str(value).strip() != ''
        ),
        None,
    )
    cluster_not_ready = sum(_integer(item.get('not_ready_nodes')) for item in clusters)
    cluster_ready = sum(_integer(item.get('ready_nodes')) for item in clusters)
    if explicit_not_ready is not None:
        not_ready = max(0, min(totals['nodes'], explicit_not_ready))
    elif explicit_ready is not None:
        not_ready = max(0, totals['nodes'] - explicit_ready)
    elif cluster_not_ready > 0 or cluster_ready > 0:
        not_ready = cluster_not_ready if cluster_not_ready > 0 else max(0, totals['nodes'] - cluster_ready)
    else:
        # Cluster-health counts are not node-readiness counts. Do not infer node
        # readiness from healthy_clusters.
        not_ready = 0
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
        'health_summary': ' '.join(_inventory_health_summary(inventory_snapshot, clusters)),
        'notes': (
            'Inventory values represent the latest committed generation for each asset type.',
            'This overview summarizes long resource identities; complete asset records remain available in Kubernetes Inventory.',
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
        'freshness_svg': _freshness_svg(freshness),
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


def _freshness_svg(freshness: Mapping[str, Any]) -> str:
    raw_history = (
        _sequence(freshness.get('history'))
        or _sequence(freshness.get('freshness_history'))
        or _sequence(freshness.get('trend'))
    )
    values: list[float] = []
    labels: list[str] = []
    for index, item in enumerate(raw_history[:12]):
        row = _mapping(item)
        raw_value = row.get('percent') or row.get('value') or row.get('freshness')
        if raw_value is None:
            continue
        values.append(max(0.0, min(_number(raw_value), 100.0)))
        labels.append(_text(row.get('label') or row.get('timestamp') or row.get('date'), f'T{index + 1}'))
    if len(values) < 2:
        return (
            '<svg class="ao-chart-svg freshness-empty" viewBox="0 0 640 150" preserveAspectRatio="none" '
            'role="img" aria-label="Freshness history not available">'
            '<rect x="0" y="0" width="640" height="150" fill="#f8fafc"/>'
            '<line x1="36" y1="112" x2="604" y2="112" stroke="#cbd5e1" stroke-width="1"/>'
            '<text x="320" y="68" text-anchor="middle" font-size="13" font-family="Inter, Arial" fill="#475569">Historical freshness trend is not available</text>'
            '<text x="320" y="91" text-anchor="middle" font-size="10" font-family="Inter, Arial" fill="#64748b">Current source freshness remains available in the table below.</text>'
            '</svg>'
        )

    left, right, top, bottom = 42.0, 606.0, 18.0, 116.0
    step = (right - left) / (len(values) - 1)
    points = []
    for index, value in enumerate(values):
        x = left + index * step
        y = bottom - (value / 100.0) * (bottom - top)
        points.append((x, y))
    point_text = ' '.join(f'{x:.2f},{y:.2f}' for x, y in points)
    first_label = escape(labels[0])
    last_label = escape(labels[-1])
    return (
        '<svg class="ao-chart-svg" viewBox="0 0 640 150" preserveAspectRatio="none" role="img" aria-label="Freshness over time">'
        '<rect x="0" y="0" width="640" height="150" fill="#ffffff"/>'
        '<g stroke="#e5e7eb" stroke-width="1">'
        '<line x1="42" y1="18" x2="606" y2="18"/><line x1="42" y1="67" x2="606" y2="67"/><line x1="42" y1="116" x2="606" y2="116"/>'
        '</g>'
        '<g fill="#64748b" font-size="9" font-family="Inter, Arial"><text x="12" y="21">100%</text><text x="18" y="70">50%</text><text x="24" y="119">0%</text></g>'
        f'<polyline points="{point_text}" fill="none" stroke="#7c3aed" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="4" fill="#7c3aed"/>'
        f'<g fill="#64748b" font-size="9" font-family="Inter, Arial"><text x="42" y="140">{first_label}</text><text x="606" y="140" text-anchor="end">{last_label}</text></g>'
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
                'register_title': 'Maintain Current Posture',
                'description': 'No actionable recommendation was returned for the current reporting boundary.',
                'recommended_action': 'Continue monitoring committed evidence and validate the next reporting cut-off.',
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
            'Top-consumer sections show leading contributors only; complete rankings and full identities remain available in KAORI detail views.',
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
