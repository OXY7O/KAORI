from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    RESOURCE_COLUMNS,
    TREND_COLUMNS,
    clean_unit,
    column,
    first,
    leading_percent_readout,
    mapping,
    metric_value,
    normalized_consumer_value,
    number,
    sequence,
    source_evidence_table,
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


def _trend_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    trends = mapping(payload.get('trends'))
    series_by_key = {key: sequence(trends.get(key)) for key in ('cpu', 'memory', 'pods', 'storage')}
    count = max((len(rows) for rows in series_by_key.values()), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        row: dict[str, Any] = {'observation': index + 1, 'timestamp': ''}
        for key in ('cpu', 'memory', 'pods', 'storage'):
            item = series_by_key[key][index] if index < len(series_by_key[key]) else {}
            row[f'{key}_percent'] = number(first(item, 'percent', 'value'))
            if not row['timestamp']:
                row['timestamp'] = first(item, 'timestamp', 'time', 'observed_at', default='')
        rows.append(row)
    return rows


def _consumer_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource, key, default_unit in (
        ('CPU', 'top_cpu_consumers', 'cores'),
        ('Memory', 'top_memory_consumers', 'GiB'),
    ):
        for item in sequence(payload.get(key)):
            raw_value = number(first(item, 'value', 'current_usage', 'percent'))
            display_value = first(item, 'current_display', 'display_value', default=raw_value)
            unit = clean_unit(first(item, 'unit', default=default_unit)) or default_unit
            rows.append(
                {
                    'resource': resource,
                    'namespace': first(item, 'namespace', default='Not Available'),
                    'consumer': first(item, 'pod', 'name', 'workload', default='Not Available'),
                    'value': normalized_consumer_value(
                        resource=resource,
                        raw_value=raw_value,
                        display_value=display_value,
                        unit=unit,
                    ),
                    'unit': unit,
                }
            )
    return rows


def _chart(trend_rows: list[dict[str, Any]]) -> AnalyticsChartData | None:
    if not trend_rows:
        return None
    series = tuple(
        AnalyticsChartSeries(key=f'{key}_percent', label=label, number_format='0.0', unit='%')
        for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('pods', 'Pods'), ('storage', 'Storage'))
        if any(row.get(f'{key}_percent') is not None for row in trend_rows)
    )
    if not series:
        return None
    category_key = 'timestamp' if all(text(row.get('timestamp'), '') for row in trend_rows) else 'observation'
    return AnalyticsChartData(
        title='Resource Utilization Trend',
        visual_type='line',
        source_sheet='Trends',
        rows=tuple(trend_rows),
        category_key=category_key,
        series=series,
        value_axis_title='Utilization (%)',
    )


def prepare_resource_utilization(
    payload: Mapping[str, Any],
    context: AnalyticsExportContext,
    profile: AnalyticsWorkbookProfile,
) -> AnalyticsWorkbookData:
    summary = mapping(payload.get('summary'))
    risk = mapping(payload.get('risk_assessment'))
    values = (
        number(summary.get('cpu_utilization')),
        number(summary.get('memory_utilization')),
        number(summary.get('storage_utilization')),
        number(summary.get('pod_utilization')),
    )
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    analysis_rows = [
        {
            'resource': label,
            'current_percent': value,
            'headroom_percent': (100.0 - value) if value is not None else None,
            'status': first(mapping(risk.get(key)), 'status', 'label', default='Not Available'),
        }
        for label, key, value in zip(
            ('CPU', 'Memory', 'Storage', 'Pods'),
            ('cpu', 'memory', 'storage', 'pods'),
            values,
            strict=True,
        )
    ]
    tables: list[AnalyticsTableData] = [
        table(
            'Analysis',
            'Resource Utilization Analysis',
            'Current committed utilization and headroom by resource.',
            RESOURCE_COLUMNS,
            analysis_rows,
        )
    ]

    trend_rows = _trend_rows(payload)
    if trend_rows:
        tables.append(table('Trends', 'Utilization Trends', 'Committed utilization series in source order.', TREND_COLUMNS, trend_rows))

    consumer_rows = _consumer_rows(payload)
    if consumer_rows:
        tables.append(
            table(
                'Top Consumers',
                'Leading Resource Consumers',
                'Committed leading consumer evidence. CPU and memory values retain their source units.',
                (
                    column('resource', 'Resource', 'Resource signal used for ranking.', width=14),
                    column('namespace', 'Namespace', 'Kubernetes namespace.', width=28),
                    column('consumer', 'Consumer', 'Pod, workload, or resource identity.', width=44),
                    column('value', 'Value', 'Committed resource value.', data_type='number', number_format='#,##0.00', width=16),
                    column('unit', 'Unit', 'Unit supplied by the source evidence.', width=12),
                ),
                consumer_rows,
            )
        )
    evidence = source_evidence_table(payload)
    if evidence is not None:
        tables.append(evidence)

    return AnalyticsWorkbookData(
        profile,
        context,
        metrics,
        leading_percent_readout(metrics, 'utilization'),
        tuple(tables),
        _chart(trend_rows),
    )
