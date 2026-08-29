from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    GIB,
    column,
    first,
    integer,
    mapping,
    metric_value,
    number,
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


def _parse_gib(item: Mapping[str, Any]) -> float | None:
    for key in ('usage_gib', 'size_gib', 'used_gib'):
        value = number(item.get(key))
        if value is not None:
            return value
    bytes_value = number(first(item, 'usage_bytes', 'size_bytes', 'used_bytes'))
    if bytes_value is not None:
        return bytes_value / GIB
    display = first(item, 'usage_display', 'size_display', 'current_display')
    parsed = number(display)
    if parsed is None:
        return None
    rendered = text(display, '').casefold()
    if 'tib' in rendered:
        return parsed * 1024.0
    if 'mib' in rendered:
        return parsed / 1024.0
    return parsed


def _consumer_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            'bucket': first(item, 'name', 'bucket', default='Unknown Bucket'),
            'usage_gib': _parse_gib(item),
            'objects': integer(first(item, 'object_count', 'objects', default=0)),
            'quota': first(item, 'quota_display', 'quota', default='Not Available'),
            'usage_share': number(item.get('usage_share')),
        }
        for item in sequence(payload.get('top_consumers') or payload.get('bucket_rows'))
    ]
    rows.sort(key=lambda row: float(row['usage_gib'] or 0), reverse=True)
    return rows


def _forecast_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    forecast = mapping(payload.get('forecast_display'))
    if not forecast:
        return []
    return [
        {
            'observation': index,
            'timestamp': first(item, 'timestamp', 'date', default=''),
            'historical_gib': number(first(item, 'historical_gib', 'historical', 'current_gib')),
            'forecast_gib': number(first(item, 'forecast_gib', 'forecast', 'projected_gib')),
        }
        for index, item in enumerate(sequence(forecast.get('series') or forecast.get('rows')), start=1)
    ]


def _alert_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            'name': first(item, 'name', 'alertname', 'label', default='Not Available'),
            'severity': first(item, 'severity', default='Unknown'),
            'status': first(item, 'status', 'state', default='Not Available'),
            'resource': first(item, 'resource', 'bucket', default='Not Available'),
        }
        for item in sequence(payload.get('alerts'))
    ]


def _append_optional_tables(
    tables: list[AnalyticsTableData],
    consumers: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
    alert_rows: list[dict[str, Any]],
) -> None:
    if consumers:
        tables.append(
            table(
                'Top Consumers',
                'Object Storage Consumers',
                'Bucket/container usage ranking normalized to GiB when numeric usage evidence is available.',
                (
                    column('bucket', 'Bucket / Container', 'Bucket or container identity.', width=44),
                    column('usage_gib', 'Usage GiB', 'Committed usage normalized to GiB.', data_type='number', number_format='#,##0.00', unit='GiB', width=16),
                    column('objects', 'Objects', 'Committed object count.', data_type='integer', number_format='#,##0', width=16),
                    column('quota', 'Quota', 'Committed quota evidence.', width=20),
                    column('usage_share', 'Usage Share %', 'Committed usage share when supplied.', data_type='percent', number_format='0.0"%"', width=16),
                ),
                consumers,
            )
        )
    if forecast_rows:
        tables.append(
            table(
                'Trends',
                'Object Storage Growth & Forecast',
                'Committed historical and forecast evidence; Excel does not calculate the forecast.',
                (
                    column('observation', 'Observation', 'Source-order point.', data_type='integer', number_format='#,##0', width=14),
                    column('timestamp', 'Timestamp', 'Committed timestamp.', width=22),
                    column('historical_gib', 'Historical GiB', 'Committed historical usage.', data_type='number', number_format='#,##0.00', unit='GiB', width=18),
                    column('forecast_gib', 'Forecast GiB', 'Committed forecast usage.', data_type='number', number_format='#,##0.00', unit='GiB', width=18),
                ),
                forecast_rows,
            )
        )
    if alert_rows:
        tables.append(
            table(
                'Alerts & Anomalies',
                'Object Storage Alert Evidence',
                'Committed alert evidence associated with the selected Object Storage system.',
                (
                    column('name', 'Signal', 'Alert identity.', width=38),
                    column('severity', 'Severity', 'Committed severity.', width=16),
                    column('status', 'Status', 'Committed alert state.', width=16),
                    column('resource', 'Resource', 'Affected bucket/system resource.', width=34),
                ),
                alert_rows,
            )
        )


def _chart(consumers: list[dict[str, Any]]) -> AnalyticsChartData | None:
    chart_rows = tuple({'category': row['bucket'], 'value': row['usage_gib']} for row in consumers[:8] if row['usage_gib'] is not None)
    if not chart_rows:
        return None
    total_value = sum(float(row['usage_gib']) for row in consumers if row['usage_gib'] is not None)
    return AnalyticsChartData(
        title='Top Object Storage Consumers',
        visual_type='ranked_bar',
        source_sheet='Top Consumers',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', 'Usage', '#,##0.00', 'GiB'),),
        value_axis_title='Usage (GiB)',
        total_value=total_value or None,
    )


def prepare_object_storage(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    summary = mapping(payload.get('summary'))
    values = (
        first(summary, 'capacity', default='Not Available'),
        first(summary, 'usage', default='Not Available'),
        first(summary, 'headroom', default='Not Available'),
        first(summary, 'utilization', default='Not Available'),
    )
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    capacity = mapping(payload.get('capacity_usage'))
    performance = mapping(payload.get('performance'))
    analysis_rows = [
        {'metric': 'Capacity', 'value': first(capacity, 'capacity_total', default=values[0])},
        {'metric': 'Usage', 'value': first(capacity, 'usage_total', default=values[1])},
        {'metric': 'Headroom', 'value': first(capacity, 'capacity_free', default=values[2])},
        {'metric': 'Utilization', 'value': first(capacity, 'utilization', default=values[3])},
        {'metric': 'Request Rate', 'value': first(performance, 'request_rate', default='Not Available')},
        {'metric': 'Error Ratio', 'value': first(performance, 'error_ratio', default='Not Available')},
        {'metric': 'Traffic', 'value': first(performance, 'traffic', default='Not Available')},
    ]
    tables: list[AnalyticsTableData] = [
        table(
            'Analysis',
            'Object Storage Analytics Summary',
            'Capacity and request-path evidence for the selected Object Storage system.',
            (
                column('metric', 'Metric', 'Analytics metric.', width=28),
                column('value', 'Value', 'Committed analytics value.', width=30),
            ),
            analysis_rows,
        )
    ]
    consumers = _consumer_rows(payload)
    _append_optional_tables(tables, consumers, _forecast_rows(payload), _alert_rows(payload))
    if consumers and consumers[0]['usage_gib'] is not None:
        readout = f'{consumers[0]["bucket"]} is the leading committed storage consumer at {float(consumers[0]["usage_gib"]):.2f} GiB.'
    else:
        readout = 'No committed bucket/container usage ranking is available for the selected reporting boundary.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), _chart(consumers))
