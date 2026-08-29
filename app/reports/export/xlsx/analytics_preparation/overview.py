from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    FORECAST_POSTURE_COLUMNS,
    RESOURCE_COLUMNS,
    append_recommendations,
    column,
    first,
    integer,
    leading_percent_readout,
    mapping,
    metric_value,
    number,
    sequence,
    table,
)
from app.reports.export.xlsx.analytics_schema import (
    AnalyticsChartData,
    AnalyticsChartSeries,
    AnalyticsExportContext,
    AnalyticsTableData,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)


def _forecast_rows(payload: Mapping[str, Any], resources: Mapping[str, Any]) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    forecast = mapping(payload.get('forecast_snapshot'))
    rows: list[dict[str, Any]] = []
    for item in sequence(forecast.get('series')):
        key = str(first(item, 'key', default='') or '').strip().lower()
        if not key:
            continue
        resource = mapping(resources.get(key))
        current = number(first(item, 'latest_percent', 'current_percent'))
        if current is None:
            current = number(first(resource, 'percent', 'value'))
        projected = number(first(item, 'projected_percent', 'forecast_percent'))
        if projected is None:
            continue
        label = first(item, 'label', default='') or {
            'cpu': 'CPU',
            'memory': 'Memory',
            'storage': 'Storage',
            'pods': 'Pods',
        }.get(key, key.replace('_', ' ').title())
        rows.append(
            {
                'resource': str(label),
                'current_percent': current,
                'projected_percent': projected,
                'change_pp': round(projected - current, 2) if current is not None else None,
                'trend': first(item, 'trend', default=first(forecast, f'{key}_trend', default='Unknown')),
                'confidence': first(item, 'confidence', default='Not Available'),
            }
        )
    return forecast, rows


def _analysis_rows(resources: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('pods', 'Pods'), ('storage', 'Storage')):
        item = mapping(resources.get(key))
        value = number(first(item, 'percent', 'value'))
        if item or value is not None:
            rows.append(
                {
                    'resource': label,
                    'current_percent': value,
                    'headroom_percent': (100.0 - value) if value is not None else None,
                    'status': first(item, 'status', 'label', default='Not Available'),
                }
            )
    return rows


def _consumer_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    consumers = mapping(payload.get('top_consumers'))
    rows: list[dict[str, Any]] = []
    for resource in ('memory', 'cpu'):
        for item in sequence(consumers.get(resource)):
            rows.append(
                {
                    'resource': resource.title(),
                    'namespace': first(item, 'namespace', default='Not Available'),
                    'consumer': first(item, 'name', 'pod', 'workload', default='Not Available'),
                    'display_value': first(item, 'display_value', 'current_display', default='Not Available'),
                    'percent': number(first(item, 'percent', 'value')),
                }
            )
    return rows


def _append_detail_tables(
    tables: list[AnalyticsTableData],
    analysis_rows: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
    consumer_rows: list[dict[str, Any]],
    alert_rows: list[Mapping[str, Any]],
) -> None:
    if analysis_rows:
        tables.append(table('Analysis', 'Cross-Domain Resource Posture', 'Committed resource snapshot across the selected analytics boundary.', RESOURCE_COLUMNS, analysis_rows))
    if forecast_rows:
        tables.append(table('Trends', 'Current & Projected Resource Posture', 'Committed latest observations and backend-owned forecast projections by resource.', FORECAST_POSTURE_COLUMNS, forecast_rows))
    if consumer_rows:
        tables.append(
            table(
                'Top Consumers',
                'Leading Consumer Signals',
                'Committed consumer signals from the analytics overview payload.',
                (
                    column('resource', 'Resource', 'Resource signal.', width=14),
                    column('namespace', 'Namespace', 'Namespace identity.', width=28),
                    column('consumer', 'Consumer', 'Consumer identity.', width=44),
                    column('display_value', 'Display Value', 'Committed formatted value.', width=18),
                    column('percent', 'Percent', 'Committed percentage when supplied.', data_type='percent', number_format='0.0"%"', width=15),
                ),
                consumer_rows,
            )
        )
    if alert_rows:
        normalized = [
            {
                'name': first(item, 'name', 'alertname', 'label', default='Not Available'),
                'severity': first(item, 'severity', default='Unknown'),
                'status': first(item, 'status', 'state', default='Not Available'),
                'namespace': first(item, 'namespace', default='All Namespaces'),
            }
            for item in alert_rows
        ]
        tables.append(
            table(
                'Alerts & Anomalies',
                'Active Alert Evidence',
                'Committed alert records included in the analytics overview.',
                (
                    column('name', 'Signal', 'Alert identity.', width=38),
                    column('severity', 'Severity', 'Committed severity.', width=16),
                    column('status', 'Status', 'Committed state.', width=16),
                    column('namespace', 'Namespace', 'Namespace scope.', width=26),
                ),
                normalized,
            )
        )


def prepare_overview(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    resources = mapping(payload.get('resource_snapshot'))
    cpu = number(first(mapping(resources.get('cpu')), 'percent', 'value'))
    memory = number(first(mapping(resources.get('memory')), 'percent', 'value'))
    forecast, forecast_rows = _forecast_rows(payload, resources)
    forecast_peak = number(first(forecast, 'highest_projected_percent', 'projected_percent'))
    if forecast_peak is None and forecast_rows:
        forecast_peak = max(row['projected_percent'] for row in forecast_rows if row['projected_percent'] is not None)

    alerts = mapping(payload.get('alerts_snapshot'))
    alert_detail = mapping(payload.get('alert_detail'))
    alert_summary = mapping(alert_detail.get('summary'))
    active_alerts = integer(
        first(
            alert_summary,
            'active_alerts',
            default=first(
                alerts,
                'firing_alerts',
                default=sum(integer(first(alerts, key, f'{key}_alerts')) for key in ('critical', 'warning', 'info')),
            ),
        )
    )
    metrics = tuple(
        metric_value(spec, value)
        for spec, value in zip(profile.metric_specs, (cpu, memory, forecast_peak, active_alerts), strict=True)
    )
    analysis_rows = _analysis_rows(resources)
    consumer_rows = _consumer_rows(payload)
    alert_rows = sequence(alert_detail.get('alerts'))
    tables: list[AnalyticsTableData] = []
    _append_detail_tables(tables, analysis_rows, forecast_rows, consumer_rows, alert_rows)
    append_recommendations(tables, payload)

    chart = None
    if forecast_rows:
        chart = AnalyticsChartData(
            title='Current vs Projected Resource Posture',
            visual_type='comparison_bar',
            source_sheet='Trends',
            rows=tuple(forecast_rows),
            category_key='resource',
            series=(
                AnalyticsChartSeries('current_percent', 'Current', '0.0', '%'),
                AnalyticsChartSeries('projected_percent', 'Projected', '0.0', '%'),
            ),
            value_axis_title='Percent',
        )
    if forecast_peak is not None:
        resource_label = str(first(forecast, 'highest_projected_resource', default='Forecast Peak') or 'Forecast Peak')
        readout = (
            f'{resource_label} is the leading committed analytics projection at {forecast_peak:.1f}%. '
            'Review the Current vs Projected evidence before taking action.'
        )
    else:
        readout = leading_percent_readout(metrics[:2], 'analytics')
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)
