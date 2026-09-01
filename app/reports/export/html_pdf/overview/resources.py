from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import display_percent, integer, mapping, nested_number, number, percent, status, text, tone
from .forecast import forecast_rows


def _metric_tone(value: float | None) -> str:
    if value is None:
        return 'neutral'
    if value >= 85.0:
        return 'critical'
    if value >= 70.0:
        return 'warning'
    return 'normal'


def _set_metric_percent(
    metric: Mapping[str, Any],
    value: float | None,
    *,
    source_note: str,
) -> dict[str, Any]:
    result = dict(metric)
    if value is None:
        return result
    value = max(0.0, min(float(value), 100.0))
    metric_tone = _metric_tone(value)
    result.update(
        {
            'value': display_percent(value),
            'percent': value,
            'chart_percent': value,
            'headroom_percent': max(0.0, 100.0 - value),
            'available': True,
            'status': (
                'Critical' if metric_tone == 'critical' else 'Warning' if metric_tone == 'warning' else 'Normal'
            ),
            'tone': metric_tone,
            'description': source_note,
        }
    )
    return result


def reconcile_resource_metrics(
    metrics: Mapping[str, Mapping[str, Any]],
    *,
    forecast_series: Sequence[Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    capacity_snapshot: Mapping[str, Any],
    inventory_snapshot: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    result = {key: dict(value) for key, value in metrics.items()}
    series_map = {str(item.get('key') or '').lower(): item for item in forecast_series}

    for key in ('cpu', 'memory'):
        metric = result.get(key, {})
        current = metric.get('percent') if metric.get('available') else None
        latest = number(mapping(series_map.get(key)).get('latest_percent'), -1.0)
        if latest >= 0.0 and (current is None or (current <= 0.0 and latest >= 0.5)):
            result[key] = _set_metric_percent(
                metric,
                latest,
                source_note=(
                    f'{text(metric.get("label"), key.title())} utilization from the latest committed observation.'
                ),
            )

    storage_used = nested_number(
        storage_snapshot,
        ('used_percent',),
        ('utilization_percent',),
        ('usage_percent',),
    )
    if storage_used is None and storage_snapshot.get('free_percent') is not None:
        storage_used = max(0.0, 100.0 - number(storage_snapshot.get('free_percent')))
    storage_metric = result.get('storage', {})
    storage_current = storage_metric.get('percent') if storage_metric.get('available') else None
    if storage_used is not None and (storage_current is None or (storage_current <= 0.0 and storage_used >= 0.5)):
        result['storage'] = _set_metric_percent(
            storage_metric,
            storage_used,
            source_note='Storage utilization derived from committed requested and free-capacity evidence.',
        )

    pods_percent = nested_number(
        capacity_snapshot,
        ('pod_utilization_percent',),
        ('pods_percent',),
        ('pod_usage_percent',),
        ('pods', 'percent'),
        ('pod_capacity', 'used_percent'),
    )
    if pods_percent is None:
        remaining = nested_number(
            capacity_snapshot,
            ('pod_capacity_remaining',),
            ('pods_remaining',),
            ('pod_capacity', 'remaining'),
        )
        used = nested_number(inventory_snapshot, ('total_pods',))
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
    normalized = status(value, '').strip().lower()
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


def metric_evidence_state(
    payload: Mapping[str, Any],
    snapshot_summary: Mapping[str, Any],
) -> dict[str, Any]:
    metrics_source = mapping(payload.get('metrics_source'))
    candidates = (
        metrics_source.get('status_label'),
        metrics_source.get('status'),
        snapshot_summary.get('status'),
    )
    first_problem = next((value for value in candidates if _unavailable_state(value)), None)
    if first_problem is not None:
        return {
            'available': False,
            'status': status(first_problem, 'Source Unavailable'),
            'tone': tone(first_problem),
        }
    return {'available': True, 'status': 'Current', 'tone': 'normal'}


def resource_metrics(
    resource_snapshot: Mapping[str, Any],
    *,
    evidence_state: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    evidence_state = mapping(evidence_state)
    evidence_available = evidence_state.get('available') is not False
    for key, label in (
        ('cpu', 'CPU'),
        ('memory', 'Memory'),
        ('storage', 'Node Filesystem'),
        ('pods', 'Pods'),
    ):
        card = mapping(resource_snapshot.get(key))
        current_percent = percent(card)
        card_status = status(card.get('status'), '')
        available = (
            bool(card) and current_percent is not None and evidence_available and not _unavailable_state(card_status)
        )
        if current_percent is not None and available:
            metric_tone = tone(card.get('tone') or card.get('status'))
            current_status = card_status or 'Current'
            description = text(card.get('description'), f'{label} utilization at the report cut-off.')
            headroom = max(0.0, 100.0 - current_percent)
        else:
            current_percent = None
            headroom = None
            current_status = status(evidence_state.get('status'), card_status or 'Not Available')
            metric_tone = tone(evidence_state.get('tone') or current_status)
            description = (
                f'{label} utilization is not available because the committed metric evidence is '
                f'{current_status.lower()}.'
            )
        result[key] = {
            'key': key,
            'label': label,
            'value': display_percent(current_percent),
            'percent': current_percent,
            'chart_percent': current_percent if current_percent is not None else 0.0,
            'headroom_percent': headroom,
            'available': available,
            'status': current_status,
            'tone': metric_tone,
            'description': description,
        }
    return result


def executive_metric(metrics: Mapping[str, Mapping[str, Any]], key: str, label: str) -> dict[str, Any]:
    item = mapping(metrics.get(key))
    return {
        'label': label,
        'value': text(item.get('value')),
        'status': text(item.get('status')),
        'tone': tone(item.get('tone')),
        'note': text(item.get('description'), ''),
    }


def storage_headroom_metric(storage: Mapping[str, Any]) -> dict[str, Any]:
    free = None
    if storage.get('free_percent') is not None:
        free = max(0.0, min(number(storage.get('free_percent')), 100.0))
    elif storage.get('used_percent') is not None:
        free = max(0.0, 100.0 - number(storage.get('used_percent')))
    risks = integer(storage.get('pvc_risk_count'))
    if free is None:
        metric_tone = 'warning' if risks else 'neutral'
        metric_status = 'Review' if risks else 'Not Available'
    else:
        metric_tone = 'critical' if free < 10 else 'warning' if risks or free < 30 else 'normal'
        metric_status = 'Critical' if metric_tone == 'critical' else 'Review' if metric_tone == 'warning' else 'Normal'
    return {
        'label': 'PVC Headroom',
        'value': display_percent(free),
        'status': metric_status,
        'tone': metric_tone,
        'note': f'{risks} local storage risk item(s).' if risks else 'Aggregate free capacity at the report cut-off.',
    }


def resource_posture_card(metrics: Mapping[str, Mapping[str, Any]], key: str) -> dict[str, Any]:
    metric = mapping(metrics.get(key))
    current = metric.get('percent') if metric.get('available') else None
    return {
        **metric,
        'current': display_percent(current),
        'p95': display_percent(current),
        'headroom': display_percent(max(0.0, 100.0 - current) if current is not None else None),
        'chart_percent': current if current is not None else 0.0,
        'warning_threshold': 70,
        'critical_threshold': 85,
    }


def capacity_rows(
    *,
    resource_metrics: Mapping[str, Mapping[str, Any]],
    capacity_snapshot: Mapping[str, Any],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    storage_free = number(storage_snapshot.get('free_percent'))
    pods_metric = mapping(resource_metrics.get('pods'))
    node_count = integer(inventory.get('total_nodes'))
    not_ready = integer(inventory.get('not_ready_nodes'))
    pods_used_count = integer(mapping(inventory.get('totals')).get('pods'))
    pods_remaining = nested_number(
        capacity_snapshot,
        ('pod_capacity_remaining',),
        ('pods_remaining',),
        ('pod_capacity', 'remaining'),
    )
    pods_total = (
        pods_used_count + int(round(pods_remaining or 0)) if pods_used_count and pods_remaining is not None else 0
    )
    pods_capacity_label = (
        f'{pods_total} Total'
        if pods_total
        else text(mapping(capacity_snapshot.get('pod_capacity_remaining')).get('value'), 'Not Available')
    )
    pods_headroom_label = (
        f'{int(round(pods_remaining))} Remaining ({display_percent(pods_metric.get("headroom_percent"))})'
        if pods_remaining is not None
        else display_percent(pods_metric.get('headroom_percent'))
    )
    storage_risks = integer(storage_snapshot.get('pvc_risk_count'))
    storage_tone = tone(storage_snapshot.get('tone'))
    if storage_tone == 'neutral':
        storage_tone = 'warning' if storage_risks or storage_free < 30.0 else 'normal'
    storage_status = status(storage_snapshot.get('status'), '')
    if not storage_status:
        storage_status = (
            'Review' if storage_tone == 'warning' else 'Critical' if storage_tone == 'critical' else 'Normal'
        )
    storage_used_percent = max(0.0, min(100.0, 100.0 - storage_free))
    return [
        {
            'resource': 'PVC Storage',
            'used': text(storage_snapshot.get('pvc_used'), 'Not Available'),
            'capacity': text(
                storage_snapshot.get('pvc_capacity') or storage_snapshot.get('pvc_requested'),
                'Not Available',
            ),
            'headroom': display_percent(storage_free),
            'chart_percent': storage_used_percent,
            'chart_value': f'{display_percent(storage_used_percent)} used',
            'chart_headroom': f'{display_percent(storage_free)} headroom',
            'interpretation': (
                f'{storage_risks} PVC pressure or expansion risk item(s) detected.'
                if storage_risks
                else 'Observed PVC usage remains within the current capacity baseline.'
            ),
            'status': storage_status,
            'tone': storage_tone,
        },
        {
            'resource': 'Pods',
            'used': text(pods_metric.get('value')),
            'capacity': pods_capacity_label,
            'headroom': pods_headroom_label,
            'chart_percent': number(pods_metric.get('percent')),
            'chart_value': f'{text(pods_metric.get("value"))} used',
            'chart_headroom': f'{display_percent(pods_metric.get("headroom_percent"))} headroom',
            'interpretation': 'Current pod utilization and remaining schedulable slots.',
            'status': text(pods_metric.get('status')),
            'tone': tone(pods_metric.get('tone')),
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


def resource_interpretation(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> str:
    available_metrics = [item for item in resource_metrics.values() if item.get('available')]
    highest = max(available_metrics, key=lambda item: number(item.get('percent')), default={})
    pvc_risks = integer(storage_snapshot.get('pvc_risk_count'))
    not_ready = integer(inventory.get('not_ready_nodes'))
    if highest:
        highest_label = text(highest.get('label'), 'Resource')
        highest_percent = number(highest.get('percent'))
        if highest_percent < 0.5:
            details = [
                'Shared-resource utilization is below 0.5%; source recency should be validated before operational use.'
            ]
        else:
            details = [
                f'{highest_label} is the highest available shared resource signal at '
                f'{display_percent(highest_percent)}.'
            ]
    else:
        details = ['Shared CPU and memory signals are not available from the committed metric evidence.']
    pvc_headroom = storage_snapshot.get('free_percent')
    if pvc_headroom is not None:
        details.append(f'Observed PVC headroom is {display_percent(number(pvc_headroom))}.')
    if pvc_risks:
        details.append(f'{pvc_risks} PVC item(s) require separate review.')
    if not_ready:
        details.append(f'{not_ready} node(s) are not ready and are excluded from active capacity assumptions.')
    return ' '.join(details)


def capacity_pressure_rows(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    capacity_snapshot: Mapping[str, Any],
    storage_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('storage', 'Node Filesystem'), ('pods', 'Pods')):
        metric = mapping(resource_metrics.get(key))
        available = bool(metric.get('available'))
        current_percent = metric.get('percent') if available else None
        headroom = display_percent(max(0.0, 100.0 - current_percent) if current_percent is not None else None)
        rows.append(
            {
                'resource': label,
                'used': display_percent(current_percent),
                'capacity': '100% reference' if available else 'Not Available',
                'headroom': headroom,
                'percent': current_percent if current_percent is not None else 0.0,
                'status': text(metric.get('status')),
                'tone': tone(metric.get('tone')),
            }
        )
    pvc_used = storage_snapshot.get('used_percent')
    pvc_free = storage_snapshot.get('free_percent')
    pvc_available = pvc_used is not None or pvc_free is not None
    if pvc_used is None and pvc_free is not None:
        pvc_used = max(0.0, 100.0 - number(pvc_free))
    if pvc_free is None and pvc_used is not None:
        pvc_free = max(0.0, 100.0 - number(pvc_used))
    pvc_risk_count = integer(storage_snapshot.get('pvc_risk_count'))
    pvc_status = 'Review' if pvc_risk_count else 'Normal' if pvc_available else 'Unknown'
    pvc_tone = 'warning' if pvc_risk_count else 'normal' if pvc_available else 'neutral'
    rows.append(
        {
            'resource': 'PVC Storage',
            'used': display_percent(number(pvc_used)) if pvc_available else 'Not Available',
            'capacity': text(
                storage_snapshot.get('pvc_capacity') or storage_snapshot.get('pvc_requested'),
                'Not Available',
            ),
            'headroom': display_percent(number(pvc_free)) if pvc_available else 'Not Available',
            'percent': number(pvc_used) if pvc_available else 0.0,
            'status': pvc_status,
            'tone': pvc_tone,
        }
    )

    total_nodes = integer(inventory.get('total_nodes'))
    not_ready = integer(inventory.get('not_ready_nodes'))
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


def headroom_distribution(inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    clusters = inventory.get('clusters') or []
    healthy = sum(1 for item in clusters if isinstance(item, Mapping) and tone(item.get('tone')) == 'normal')
    attention = sum(1 for item in clusters if isinstance(item, Mapping) and tone(item.get('tone')) == 'warning')
    critical = sum(1 for item in clusters if isinstance(item, Mapping) and tone(item.get('tone')) == 'critical')
    unknown = max(0, len(clusters) - healthy - attention - critical)
    return [
        {'label': 'Healthy', 'value': healthy, 'tone': 'normal'},
        {'label': 'At Risk', 'value': attention, 'tone': 'warning'},
        {'label': 'Critical', 'value': critical, 'tone': 'critical'},
        {'label': 'Unknown', 'value': unknown, 'tone': 'neutral'},
    ]


def capacity_forecast_rows(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    forecast_snapshot: Mapping[str, Any],
    series: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            'resource': row['resource'],
            'range': f'{row["current"]} - {row["projected"]}',
            'pressure': 'High' if row['tone'] == 'critical' else 'Moderate' if row['tone'] == 'warning' else 'Low',
            'risk': 'Medium' if row['tone'] == 'critical' else 'Low',
            'tone': row['tone'],
        }
        for row in forecast_rows(resource_metrics, forecast_snapshot, series)
    ]


def capacity_interpretation(
    resource_metrics: Mapping[str, Mapping[str, Any]],
    inventory: Mapping[str, Any],
) -> str:
    constrained = sorted(
        (item for item in resource_metrics.values() if item.get('available') and item.get('percent') is not None),
        key=lambda item: number(item.get('percent')),
        reverse=True,
    )[:2]
    if constrained and number(constrained[0].get('percent')) >= 0.5:
        names = ' and '.join(text(item.get('label')) for item in constrained)
        base = f'{names} are the most constrained shared resources in the current committed snapshot.'
    elif constrained:
        base = (
            'Shared-resource utilization is below 0.5%; verify the current metric collection window before remediation.'
        )
    else:
        base = 'Shared-resource utilization is not available from the committed metric evidence.'
    not_ready = integer(inventory.get('not_ready_nodes'))
    suffix = f' {not_ready} node(s) are not ready.' if not_ready else ''
    return base + suffix
