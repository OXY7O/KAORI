from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.kubernetes.analytics.alerts.contracts import NormalizedAlert
from app.kubernetes.analytics.alerts.metrics import get_metric_labels
from app.kubernetes.analytics.alerts.ownership import (
    extract_alert_contact_from_payload,
    extract_alert_owner_from_payload,
    extract_alert_runbook_from_payload,
)

_SEVERITY_ALIASES = {
    'critical': 'critical',
    'fatal': 'critical',
    'error': 'critical',
    'page': 'critical',
    'p1': 'critical',
    'warning': 'warning',
    'warn': 'warning',
    'p2': 'warning',
    'info': 'info',
    'informational': 'info',
    'notice': 'info',
    'p3': 'info',
    'p4': 'info',
    'none': 'none',
    'unknown': 'none',
    '': 'none',
}

_STATUS_ALIASES = {
    'firing': 'firing',
    'pending': 'pending',
    'active': 'active',
    'resolved': 'resolved',
    'inactive': 'resolved',
    'suppressed': 'active',
    '': 'active',
}

_IDENTITY_IGNORED_LABELS = {'__replica__', 'alertstate'}


def _identity_label_is_ignored(value: object) -> bool:
    label = str(value or '').strip().lower()
    return label in _IDENTITY_IGNORED_LABELS or label.endswith('_replica') or label.endswith('_replica_name')


def normalize_severity(value: Any) -> str:
    return _SEVERITY_ALIASES.get(str(value or '').strip().lower(), 'none')


def normalize_status(value: Any) -> str:
    return _STATUS_ALIASES.get(str(value or '').strip().lower(), 'active')


def format_alert_datetime(value: Any) -> str:
    if value is None:
        return '-'

    text_value = str(value).strip()
    if not text_value or text_value == '-':
        return '-'

    try:
        parsed_value = datetime.fromisoformat(text_value.replace('Z', '+00:00'))
        return parsed_value.strftime('%Y-%m-%d %H:%M')
    except ValueError:
        return text_value[:16]


def normalize_alertmanager_item(item: dict[str, Any]) -> NormalizedAlert:
    labels = item.get('labels', {})
    if not isinstance(labels, dict):
        labels = {}

    annotations = item.get('annotations', {})
    if not isinstance(annotations, dict):
        annotations = {}

    status_payload = item.get('status', {})
    if not isinstance(status_payload, dict):
        status_payload = {}

    starts_at = item.get('starts_at') or item.get('startsAt')
    ends_at = item.get('ends_at') or item.get('endsAt')
    alert_name = item.get('alertname') or labels.get('alertname') or item.get('name') or 'Unknown Alert'
    severity = normalize_severity(item.get('severity') or labels.get('severity'))
    raw_status = item.get('status') if isinstance(item.get('status'), str) else status_payload.get('state', 'active')
    status = normalize_status(raw_status)
    namespace = item.get('namespace') or labels.get('namespace') or '-'
    target = (
        item.get('pod') or labels.get('pod') or labels.get('node') or labels.get('instance') or labels.get('job') or '-'
    )
    summary = item.get('summary') or annotations.get('summary') or annotations.get('message') or '-'
    description = item.get('description') or annotations.get('description') or summary

    return {
        'name': str(alert_name),
        'severity': severity,
        'status': status,
        'namespace': str(namespace),
        'target': str(target),
        'source': 'Alertmanager',
        'summary': str(summary),
        'description': str(description),
        'starts_at': starts_at or '-',
        'starts_at_display': format_alert_datetime(starts_at),
        'ends_at': ends_at or '-',
        'ends_at_display': format_alert_datetime(ends_at),
        'labels': labels,
        'annotations': annotations,
        'generator_url': item.get('generatorURL') or item.get('generator_url') or '',
        'fingerprint': item.get('fingerprint', ''),
        'receiver': item.get('receiver', '-'),
        'owner': extract_alert_owner_from_payload(
            labels=labels,
            annotations=annotations,
            fallback_namespace=str(namespace),
        ),
        'runbook_url': extract_alert_runbook_from_payload(annotations=annotations),
        'contact': extract_alert_contact_from_payload(labels=labels, annotations=annotations),
        'silenced': bool(item.get('silenced', False)) or bool(status_payload.get('silencedBy', [])),
        'inhibited': bool(item.get('inhibited', False)) or bool(status_payload.get('inhibitedBy', [])),
        'silenced_by': item.get('silenced_by', status_payload.get('silencedBy', [])),
        'inhibited_by': item.get('inhibited_by', status_payload.get('inhibitedBy', [])),
    }


def normalize_metrics_source_alert(item: dict[str, Any]) -> NormalizedAlert:
    metric = get_metric_labels(item)
    value = item.get('value', [])
    alert_value = str(value[1]) if isinstance(value, list) and len(value) >= 2 else '-'
    alert_name = str(metric.get('alertname') or 'Unknown Alert')
    namespace = str(metric.get('namespace') or '-')
    target = str(metric.get('pod') or metric.get('node') or metric.get('instance') or metric.get('job') or '-')

    return {
        'name': alert_name,
        'severity': normalize_severity(metric.get('severity')),
        'status': normalize_status(metric.get('alertstate') or 'firing'),
        'namespace': namespace,
        'target': target,
        'source': 'Metrics Source',
        'summary': alert_name,
        'description': 'Alert loaded from the Metrics Source ALERTS metric.',
        'starts_at': '-',
        'starts_at_display': '-',
        'ends_at': '-',
        'ends_at_display': '-',
        'labels': metric,
        'annotations': {},
        'owner': extract_alert_owner_from_payload(
            labels=metric,
            annotations={},
            fallback_namespace=namespace,
        ),
        'runbook_url': '',
        'contact': extract_alert_contact_from_payload(labels=metric, annotations={}),
        'generator_url': '',
        'fingerprint': '',
        'value': alert_value,
    }


def _canonical_labels(labels: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(labels, dict):
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in labels.items() if not _identity_label_is_ignored(key)))


def alert_identity(alert: NormalizedAlert) -> tuple[Any, ...]:
    fingerprint = str(alert.get('fingerprint') or '').strip()
    if fingerprint:
        return ('fingerprint', fingerprint)
    return (
        str(alert.get('source') or '').lower(),
        str(alert.get('name') or '').lower(),
        str(alert.get('namespace') or '').lower(),
        str(alert.get('target') or '').lower(),
        _canonical_labels(alert.get('labels')),
    )


def _alert_priority(alert: NormalizedAlert) -> tuple[int, int, int]:
    severity_rank = {'critical': 4, 'warning': 3, 'info': 2, 'none': 1}
    status_rank = {'firing': 4, 'pending': 3, 'active': 2, 'resolved': 1}
    return (
        severity_rank.get(str(alert.get('severity') or 'none'), 0),
        status_rank.get(str(alert.get('status') or 'active'), 0),
        0 if alert.get('silenced') or alert.get('inhibited') else 1,
    )


def deduplicate_alerts(alerts: Iterable[NormalizedAlert]) -> list[NormalizedAlert]:
    selected: dict[tuple[Any, ...], NormalizedAlert] = {}
    order: list[tuple[Any, ...]] = []
    for alert in alerts:
        identity = alert_identity(alert)
        current = selected.get(identity)
        if current is None:
            order.append(identity)
            selected[identity] = alert
            continue
        if _alert_priority(alert) > _alert_priority(current):
            selected[identity] = alert
    return [selected[identity] for identity in order]


def filter_items(
    items: list[NormalizedAlert],
    *,
    severity: str,
    status: str,
    namespace: str,
    search: str,
) -> list[NormalizedAlert]:
    filtered = items

    if severity != 'all':
        filtered = [item for item in filtered if str(item.get('severity', '')).lower() == severity]

    if status != 'all':
        filtered = [item for item in filtered if str(item.get('status', '')).lower() == status]

    if namespace:
        namespace_query = namespace.strip().lower()
        filtered = [item for item in filtered if str(item.get('namespace', '')).strip().lower() == namespace_query]

    if search:
        search_query = search.lower()
        filtered = [
            item
            for item in filtered
            if search_query
            in ' '.join(
                [
                    str(item.get('name', '')),
                    str(item.get('namespace', '')),
                    str(item.get('target', '')),
                    str(item.get('summary', '')),
                    str(item.get('description', '')),
                ]
            ).lower()
        ]

    return filtered
