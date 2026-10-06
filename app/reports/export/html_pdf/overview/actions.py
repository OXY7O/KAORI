from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import display_percent, integer, mapping, number, sequence, text, tone


def priority_findings(
    *,
    resource_metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    workload_snapshot: Mapping[str, Any],
    forecast_snapshot: Mapping[str, Any],
    alerts_snapshot: Mapping[str, Any],
    recommendations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    findings = _recommendation_findings(recommendations)
    if not findings:
        findings.extend(_resource_findings(resource_metrics))
    _append_storage_finding(findings, storage_snapshot)
    _append_workload_finding(findings, workload_snapshot)
    _append_forecast_finding(findings, forecast_snapshot)
    _append_alert_finding(findings, alerts_snapshot)
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


def _recommendation_findings(recommendations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'title': text(item.get('title'), 'Operational recommendation'),
            'description': text(item.get('description'), ''),
            'summary': text(item.get('summary') or item.get('description'), ''),
            'priority': text(item.get('priority'), 'Review'),
            'tone': tone(item.get('tone') or item.get('priority')),
            'scope': text(item.get('scope'), 'Selected reporting scope'),
        }
        for item in recommendations[:5]
    ]


def _resource_findings(resource_metrics: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in ('memory', 'cpu', 'storage', 'pods'):
        metric = mapping(resource_metrics.get(key))
        metric_tone = tone(metric.get('tone'))
        if metric_tone not in {'warning', 'critical'}:
            continue
        findings.append(
            {
                'title': f'{text(metric.get("label"))} utilization requires review',
                'description': text(metric.get('description'), ''),
                'tone': metric_tone,
                'scope': 'Selected cluster',
            }
        )
    return findings


def _append_storage_finding(findings: list[dict[str, Any]], storage_snapshot: Mapping[str, Any]) -> None:
    pvc_risks = integer(storage_snapshot.get('pvc_risk_count'))
    if not pvc_risks:
        return
    if any('volume' in item['title'].lower() or 'storage' in item['title'].lower() for item in findings):
        return
    findings.append(
        {
            'title': f'{pvc_risks} persistent volume claim(s) require capacity review',
            'description': 'Local volume headroom is below the configured operational threshold.',
            'tone': 'warning',
            'scope': text(storage_snapshot.get('top_namespace'), 'Storage scope'),
        }
    )


def _append_workload_finding(findings: list[dict[str, Any]], workload_snapshot: Mapping[str, Any]) -> None:
    workload_issues = sum(
        integer(workload_snapshot.get(key))
        for key in (
            'missing_cpu_requests',
            'missing_memory_requests',
            'memory_limits_missing',
            'over_provisioned',
            'under_provisioned',
        )
    )
    if not workload_issues or len(findings) >= 5:
        return
    findings.append(
        {
            'title': f'{workload_issues} workload governance signal(s) require review',
            'description': 'Requests, limits, or right-sizing evidence requires operational validation.',
            'tone': 'warning',
            'scope': 'Workload analytics',
        }
    )


def _append_forecast_finding(findings: list[dict[str, Any]], forecast_snapshot: Mapping[str, Any]) -> None:
    risk_count = integer(forecast_snapshot.get('risk_count'))
    if not risk_count or len(findings) >= 5:
        return
    findings.append(
        {
            'title': f'{risk_count} forecast threshold risk item(s) detected',
            'description': text(forecast_snapshot.get('risk_note'), ''),
            'tone': tone(forecast_snapshot.get('forecast_risk')),
            'scope': text(forecast_snapshot.get('highest_projected_resource'), 'Forecast scope'),
        }
    )


def _append_alert_finding(findings: list[dict[str, Any]], alerts_snapshot: Mapping[str, Any]) -> None:
    critical_alerts = integer(alerts_snapshot.get('critical_alerts'))
    if not critical_alerts or len(findings) >= 5:
        return
    findings.append(
        {
            'title': f'{critical_alerts} critical alert(s) are active',
            'description': text(alerts_snapshot.get('highest_severity_description'), ''),
            'tone': 'critical',
            'scope': 'Alert intelligence',
        }
    )


def _management_decision_summary(item: Mapping[str, Any], title: str, description: str) -> str:
    explicit = item.get('management_decision') or item.get('summary') or item.get('decision')
    if explicit:
        return text(explicit)
    summary = description.strip()
    for marker in (
        ' Namespace:',
        ' namespace:',
        ' Pod:',
        ' pod:',
        ' Resource:',
        ' resource:',
        ' Value:',
        ' value:',
    ):
        if marker in summary:
            summary = summary.split(marker, 1)[0].rstrip(' .') + '.'
            break
    if len(summary) > 180:
        summary = summary[:177].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'
    return summary or f'Review {title.lower()} and confirm the accountable owner.'


def _register_title(title: str) -> str:
    value = text(title, 'Recommendation')
    for prefix in ('Review ', 'Validate ', 'Investigate ', 'Assess '):
        if value.lower().startswith(prefix.lower()):
            value = value[len(prefix) :].strip()
            break
    if len(value) > 48:
        value = value[:45].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'
    return value or text(title, 'Recommendation')


def recommendations(actionable: Mapping[str, Any], payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = sequence(actionable.get('items'))
    if not items:
        items = sequence(payload.get('recommendations'))

    normalized = [
        row
        for index, item in enumerate(items, start=1)
        if isinstance(item, Mapping)
        for row in (_recommendation_row(item, index),)
    ]
    priority_order = {'P1': 0, 'P2': 1, 'P3': 2}
    normalized.sort(
        key=lambda item: (
            priority_order.get(text(item.get('priority')), 9),
            integer(item.get('rank')),
        )
    )
    return normalized[:12]


def _recommendation_row(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    priority = text(item.get('priority') or item.get('severity'), 'Info')
    item_tone = _priority_tone(priority)
    source = text(item.get('source_label') or item.get('source'), 'Analytics')
    title = text(item.get('title') or item.get('label'), f'Recommendation {index}')
    description = text(
        item.get('description') or item.get('reason') or item.get('evidence'),
        'Review the related evidence and confirm the appropriate operational action.',
    )
    recommended_action = text(
        item.get('recommended_action') or item.get('action') or item.get('remediation'),
        description,
    )
    scope = text(
        item.get('affected_scope') or item.get('scope') or item.get('namespace') or item.get('resource'),
        'Selected reporting scope',
    )
    return {
        'rank': index,
        'priority': 'P1' if item_tone == 'critical' else 'P2' if item_tone == 'warning' else 'P3',
        'priority_label': priority,
        'tone': item_tone if item_tone != 'neutral' else 'info',
        'title': title,
        'register_title': _register_title(title),
        'description': description,
        'summary': _management_decision_summary(item, title, description),
        'recommended_action': recommended_action,
        'scope': scope,
        'source': source,
        'owner': text(item.get('owner'), _suggest_owner(source, title)),
        'target': text(item.get('target') or item.get('due'), _target_window(item_tone)),
        'status': text(item.get('status'), 'Open' if item_tone in {'critical', 'warning'} else 'Planned'),
        'evidence': text(item.get('evidence') or item.get('reason'), description),
        'validation': _validation_text(source, title),
    }


def _priority_tone(priority: str) -> str:
    item_tone = tone(priority)
    if item_tone == 'neutral' and priority.lower() in {'p1', 'high'}:
        return 'critical'
    if item_tone == 'neutral' and priority.lower() in {'p2', 'medium'}:
        return 'warning'
    return item_tone


def _suggest_owner(source: str, title: str) -> str:
    value = f'{source} {title}'.lower()
    if 'pod' in value or 'workload' in value or 'application' in value:
        return 'Application Owner'
    if 'node' in value or 'cluster' in value:
        return 'Cluster Owner'
    return 'Platform Operations'


def _target_window(item_tone: str) -> str:
    if item_tone == 'critical':
        return '5-7 Days'
    if item_tone == 'warning':
        return '7-14 Days'
    return '14-30 Days'


def _validation_text(source: str, title: str) -> str:
    value = f'{source} {title}'.lower()
    if 'storage' in value or 'volume' in value or 'pvc' in value:
        return 'Confirm approved targets have at least 20% free capacity and stable write behavior.'
    if 'memory' in value or 'cpu' in value or 'capacity' in value:
        return 'Confirm the metric returns below its warning threshold or an approved capacity plan exists.'
    if 'alert' in value:
        return 'Confirm the alert is cleared or acknowledged with an owner and tracked response.'
    return 'Refresh committed inventory and analytics evidence and confirm the finding is cleared.'


def decision_items(
    recommendation_items: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decisions = [
        {
            'title': text(item.get('title')),
            'description': text(item.get('summary') or item.get('description'), ''),
            'tone': tone(item.get('tone')),
        }
        for item in recommendation_items[:3]
    ]
    if decisions:
        return decisions
    return [
        {
            'title': f'Review: {text(item.get("title"))}',
            'description': text(item.get('description'), ''),
            'tone': tone(item.get('tone')),
        }
        for item in findings[:3]
    ]


def management_summary(
    *,
    resource_metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
    alerts_snapshot: Mapping[str, Any],
    forecast_snapshot: Mapping[str, Any],
    priority_findings: Sequence[Mapping[str, Any]],
) -> str:
    resource_sentence = _resource_sentence(resource_metrics)
    pvc_headroom = storage_snapshot.get('free_percent')
    pvc_sentence = (
        f'Observed PVC headroom is {display_percent(number(pvc_headroom))}.'
        if pvc_headroom is not None
        else 'Observed PVC headroom is not available.'
    )
    concern_sentence = _concern_sentence(
        inventory,
        storage_snapshot,
        alerts_snapshot,
        priority_findings,
    )
    forecast_note = text(forecast_snapshot.get('risk_note'), '')
    forecast_sentence = (
        forecast_note.rstrip('.') + '.'
        if forecast_note
        else 'Forecast conclusions remain limited to the committed historical observation window.'
    )
    return f'{resource_sentence} {pvc_sentence} {concern_sentence} {forecast_sentence}'


def _resource_sentence(resource_metrics: Mapping[str, Mapping[str, Any]]) -> str:
    available = [
        item
        for item in resource_metrics.values()
        if mapping(item).get('available') and mapping(item).get('percent') is not None
    ]
    if not available:
        return 'Shared CPU and memory utilization are not available from the committed metric evidence.'
    highest = max(available, key=lambda item: number(item.get('percent')))
    highest_percent = number(highest.get('percent'))
    if highest_percent < 0.5:
        return (
            'Shared-resource utilization is below 0.5% in the current committed snapshot; '
            'validate source recency before treating the value as an operating baseline.'
        )
    return (
        f'{text(highest.get("label"))} is the highest available shared-resource signal '
        f'at {display_percent(highest_percent)}.'
    )


def _concern_sentence(
    inventory: Mapping[str, Any],
    storage_snapshot: Mapping[str, Any],
    alerts_snapshot: Mapping[str, Any],
    priority_findings: Sequence[Mapping[str, Any]],
) -> str:
    concerns: list[str] = []
    not_ready = integer(inventory.get('not_ready_nodes'))
    if not_ready:
        concerns.append(f'{not_ready} not-ready node(s)')
    storage_risks = integer(storage_snapshot.get('pvc_risk_count'))
    if storage_risks:
        concerns.append(f'{storage_risks} local storage risk item(s)')
    critical_alerts = integer(alerts_snapshot.get('critical'))
    warning_alerts = integer(alerts_snapshot.get('warning'))
    if critical_alerts or warning_alerts:
        concerns.append(f'{critical_alerts} critical and {warning_alerts} warning alert(s)')
    if concerns:
        return 'The main review areas are ' + ', '.join(concerns) + '.'
    if priority_findings:
        return 'The current overview contains findings that require operational follow-up.'
    return 'No immediate operational risk was identified in the committed overview evidence.'


def overall_assessment(
    health_summary: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> str:
    cluster_health = mapping(health_summary.get('cluster_health'))
    description = text(cluster_health.get('description'), '')
    if description:
        return description
    primary = findings[0] if findings else {}
    return text(
        primary.get('description'),
        'No complete operational assessment is available for the selected reporting boundary.',
    )


def primary_concern(findings: Sequence[Mapping[str, Any]]) -> str:
    if not findings:
        return 'No prioritized concern was detected.'
    return text(findings[0].get('title'))


def evidence_summary(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'label': text(row.get('label')),
            'source': text(row.get('source_short') or row.get('source')),
            'status': text(row.get('status_short') or row.get('status')),
            'tone': tone(row.get('tone')),
        }
        for row in source_rows[:3]
    ]
