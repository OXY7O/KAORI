from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    append_recommendations,
    column,
    first,
    integer,
    mapping,
    metric_value,
    sequence,
    table,
    text,
)
from app.reports.export.xlsx.analytics_schema import (
    AnalyticsChartData,
    AnalyticsChartSeries,
    AnalyticsExportContext,
    AnalyticsTableData,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)


def _severity_counts(summary: Mapping[str, Any], alerts: list[Mapping[str, Any]]) -> tuple[int, int, int, int]:
    active = integer(summary.get('active_alerts')) or len(alerts)
    critical = integer(summary.get('critical_alerts'))
    warning = integer(summary.get('warning_alerts'))
    info = integer(summary.get('info_alerts'))
    if critical == 0:
        critical = sum(1 for row in alerts if text(row.get('severity'), '').casefold() == 'critical')
    if warning == 0:
        warning = sum(1 for row in alerts if text(row.get('severity'), '').casefold() == 'warning')
    if info == 0:
        info = sum(1 for row in alerts if text(row.get('severity'), '').casefold() == 'info')
    return active, critical, warning, info


def _event_rows(alerts: list[Mapping[str, Any]], anomalies: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, source in (('Alert', alerts), ('Anomaly', anomalies)):
        for item in source:
            rows.append(
                {
                    'type': kind,
                    'name': first(item, 'name', 'alertname', 'title', 'label', default='Not Available'),
                    'severity': first(item, 'severity', default='Unknown'),
                    'status': first(item, 'status', 'state', default='Not Available'),
                    'namespace': first(item, 'namespace', default='All Namespaces'),
                    'resource': first(item, 'resource', 'pod', 'workload', default='Not Available'),
                    'started_at': first(item, 'started_at', 'starts_at', 'timestamp', default='Not Available'),
                }
            )
    return rows


def prepare_alerts(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    summary = mapping(payload.get('summary'))
    alerts = sequence(payload.get('alerts'))
    anomalies = sequence(payload.get('anomalies'))
    active, critical, warning, info = _severity_counts(summary, alerts)
    anomaly_count = integer(first(summary, 'detected_anomalies', 'anomalies', default=len(anomalies)))
    values = (active, critical, warning, anomaly_count)
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    source_status = mapping(payload.get('source_status'))
    tables: list[AnalyticsTableData] = [
        table(
            'Analysis',
            'Alert Evidence Sources',
            'Source and evidence readiness for the committed alert/anomaly payload.',
            (
                column('signal', 'Signal', 'Evidence source signal.', width=28),
                column('value', 'Value', 'Committed evidence state.', width=40),
            ),
            [
                {'signal': 'Alert Source', 'value': first(source_status, 'label', 'status', default='Not Available')},
                {'signal': 'Anomaly Source', 'value': first(mapping(payload.get('anomaly_source_status')), 'label', 'status', default='Not Available')},
                {'signal': 'Committed Evidence', 'value': 'Available' if payload.get('committed_evidence_available', True) else 'Unavailable'},
            ],
        )
    ]
    events = _event_rows(alerts, anomalies)
    if events:
        tables.append(
            table(
                'Alerts & Anomalies',
                'Alert & Anomaly Records',
                'Committed alert and anomaly evidence. This sheet does not duplicate Alert Intelligence workflow state.',
                (
                    column('type', 'Type', 'Alert or anomaly evidence type.', width=14),
                    column('name', 'Signal', 'Alert or anomaly identity.', width=38),
                    column('severity', 'Severity', 'Committed severity.', width=16),
                    column('status', 'Status', 'Committed state.', width=16),
                    column('namespace', 'Namespace', 'Namespace scope.', width=26),
                    column('resource', 'Resource', 'Affected resource when supplied.', width=38),
                    column('started_at', 'Started / Observed', 'Committed start or observation timestamp.', width=24),
                ),
                events,
            )
        )
    append_recommendations(tables, payload)
    unclassified = max(active - (critical + warning + info), 0)
    severity_rows = tuple(
        {'category': label, 'value': count}
        for label, count in (('Critical', critical), ('Warning', warning), ('Info', info), ('Unclassified', unclassified))
        if count > 0
    )
    chart = None
    if severity_rows:
        chart = AnalyticsChartData(
            title='Active Alert Severity',
            visual_type='composition_bar',
            source_sheet='Alerts & Anomalies',
            rows=severity_rows,
            series=(AnalyticsChartSeries('value', 'Alerts', '#,##0'),),
            total_value=float(active) if active else None,
        )
    if active or anomaly_count:
        readout = f'{active:,} active alert(s) and {anomaly_count:,} anomaly candidate(s) are committed at the report cut-off; {critical:,} alert(s) are critical.'
    else:
        readout = 'No active alert or anomaly signal is committed for the selected reporting boundary.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)
