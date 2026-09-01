from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text


@dataclass(frozen=True, slots=True)
class AlertsState:
    payload: Mapping[str, Any]
    cluster: Mapping[str, Any]
    alerts: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    active_count: int
    critical_count: int
    warning_count: int
    info_count: int
    anomaly_count: int
    severity_rows: list[dict[str, Any]]
    category_rows: list[dict[str, Any]]
    categorized_count: int
    uncategorized_count: int
    category_coverage: float | None
    environment: str
    executive_tone: str
    executive_title: str
    executive_body: str


def build_alerts_state(payload: Mapping[str, Any]) -> AlertsState:
    summary = mapping(payload.get('summary'))
    overview = mapping(payload.get('selected_cluster_signal_overview'))
    alerts = [alert_row(item) for item in sequence(payload.get('alerts')) if isinstance(item, Mapping)]
    anomalies = [anomaly_row(item) for item in sequence(payload.get('anomalies')) if isinstance(item, Mapping)]

    active_count = first_int(summary, overview, keys=('active_alerts',))
    critical_count = first_int(summary, overview, keys=('critical_alerts',))
    warning_count = first_int(summary, overview, keys=('warning_alerts',))
    info_count = first_int(summary, overview, keys=('info_alerts',))
    anomaly_count = first_int(summary, overview, keys=('detected_anomalies', 'anomalies'))

    active_count = active_count or sum(1 for item in alerts if item['status_key'] in {'active', 'firing', 'pending'})
    critical_count = critical_count or sum(1 for item in alerts if item['severity_key'] == 'critical')
    warning_count = warning_count or sum(1 for item in alerts if item['severity_key'] == 'warning')
    info_count = info_count or sum(1 for item in alerts if item['severity_key'] == 'info')
    anomaly_count = anomaly_count or len(anomalies)

    severity_rows = build_severity_rows(critical_count, warning_count, info_count)
    category_rows = category_rows_from_alerts(alerts)
    categorized_count = sum(item['count'] for item in category_rows)
    uncategorized_count = max(active_count - categorized_count, 0)
    category_coverage = (categorized_count / active_count * 100.0) if active_count else None
    cluster = mapping(payload.get('cluster'))

    return AlertsState(
        payload=payload,
        cluster=cluster,
        alerts=alerts,
        anomalies=anomalies,
        active_count=active_count,
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        anomaly_count=anomaly_count,
        severity_rows=severity_rows,
        category_rows=category_rows,
        categorized_count=categorized_count,
        uncategorized_count=uncategorized_count,
        category_coverage=category_coverage,
        environment=sanitize_text(cluster.get('environment'), fallback='Not Available'),
        executive_tone=executive_tone(critical_count, warning_count, anomaly_count),
        executive_title=executive_title(critical_count, warning_count, anomaly_count),
        executive_body=(
            f'{active_count} active alert(s) and {anomaly_count} anomaly candidate(s) are committed at the report cut-off. '
            f'{categorized_count} active alert(s) are represented by displayed categories; '
            f'{uncategorized_count} remain outside the category summary.'
        ),
    )


def build_severity_rows(critical_count: int, warning_count: int, info_count: int) -> list[dict[str, Any]]:
    maximum = max(critical_count, warning_count, info_count, 1)
    return [
        {'label': 'Critical', 'count': critical_count, 'tone': 'critical', 'bar': bar(critical_count, maximum)},
        {'label': 'Warning', 'count': warning_count, 'tone': 'warning', 'bar': bar(warning_count, maximum)},
        {'label': 'Info', 'count': info_count, 'tone': 'info', 'bar': bar(info_count, maximum)},
    ]


def alert_row(value: Mapping[str, Any]) -> dict[str, Any]:
    labels = mapping(value.get('labels'))
    annotations = mapping(value.get('annotations'))
    severity = sanitize_text(value.get('severity') or labels.get('severity'), fallback='none').lower()
    status = sanitize_text(value.get('status'), fallback='active').lower()
    category = sanitize_text(
        value.get('category') or labels.get('category') or labels.get('domain') or labels.get('alert_category'),
        fallback='Uncategorized',
    )
    return {
        'name': sanitize_text(value.get('name') or labels.get('alertname'), fallback='Unknown Alert'),
        'severity': severity.title() if severity != 'none' else 'None',
        'severity_key': severity,
        'status': status.title(),
        'status_key': status,
        'namespace': sanitize_text(value.get('namespace') or labels.get('namespace'), fallback='Not Available'),
        'target': sanitize_text(
            value.get('target') or labels.get('pod') or labels.get('instance'), fallback='Not Available'
        ),
        'source': sanitize_text(value.get('source'), fallback='Not Available'),
        'summary': sanitize_text(
            value.get('summary')
            or annotations.get('summary')
            or value.get('description')
            or annotations.get('description'),
            fallback='No committed description.',
        ),
        'starts_at_display': sanitize_text(
            value.get('starts_at_display') or value.get('starts_at'), fallback='Not Available'
        ),
        'owner': sanitize_text(value.get('owner'), fallback='Not Available'),
        'runbook': sanitize_text(value.get('runbook_url'), fallback='Not Available'),
        'contact': sanitize_text(value.get('contact'), fallback='Not Available'),
        'category': category,
        'tone': severity_tone(severity),
    }


def anomaly_row(value: Mapping[str, Any]) -> dict[str, Any]:
    evidence = value.get('evidence') or value.get('metric') or value.get('value')
    evidence_available = evidence not in {None, '', '-', 'Not Available'}
    return {
        'name': sanitize_text(value.get('name') or value.get('title'), fallback='Unknown Anomaly'),
        'namespace': sanitize_text(value.get('namespace'), fallback='Not Available'),
        'severity': sanitize_text(value.get('severity'), fallback='warning').title(),
        'status': sanitize_text(value.get('status'), fallback='Review').title(),
        'summary': sanitize_text(
            value.get('description') or value.get('summary'), fallback='No committed anomaly description.'
        ),
        'evidence': sanitize_text(evidence, fallback='Not Available'),
        'evidence_available': evidence_available,
        'starts_at_display': sanitize_text(
            value.get('starts_at_display') or value.get('timestamp') or value.get('observed_at'),
            fallback='Not Available',
        ),
        'tone': 'warning',
    }


def category_rows_from_alerts(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(item['category'] for item in alerts if item['category'] != 'Uncategorized')
    if not counts:
        return []
    maximum = max(counts.values())
    return [{'label': label, 'count': count, 'bar': bar(count, maximum)} for label, count in counts.most_common(6)]


def executive_tone(critical_count: int, warning_count: int, anomaly_count: int) -> str:
    if critical_count:
        return 'critical'
    if warning_count or anomaly_count:
        return 'warning'
    return 'normal'


def executive_title(critical_count: int, warning_count: int, anomaly_count: int) -> str:
    if critical_count:
        return 'Critical alerts require immediate operational ownership.'
    if warning_count:
        return 'Warning alerts require operational ownership and response validation.'
    if anomaly_count:
        return 'Anomaly evidence requires review.'
    return 'No active alert or anomaly signal is committed.'


def severity_tone(severity: str) -> str:
    if severity == 'critical':
        return 'critical'
    if severity == 'warning':
        return 'warning'
    if severity == 'info':
        return 'info'
    return 'muted'


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def with_ref(item: dict[str, Any], ref: str) -> dict[str, Any]:
    row = dict(item)
    row['ref'] = ref
    return row


def bar(value: int, maximum: int) -> float:
    return min(max(value / max(maximum, 1) * 100.0, 0.0), 100.0)


def percent(value: float | None) -> str:
    return f'{value:.1f}%' if value is not None else 'Not Available'


def first_int(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for source in mappings:
        for key in keys:
            if key not in source:
                continue
            try:
                return int(source.get(key) or 0)
            except (TypeError, ValueError):
                continue
    return 0


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []
