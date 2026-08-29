from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    RESOURCE_COLUMNS,
    append_recommendations,
    column,
    first,
    leading_percent_readout,
    mapping,
    metric_value,
    number,
    percent_from_resource,
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


def _capacity_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = mapping(payload.get('capacity_summary'))
    rows: list[dict[str, Any]] = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('pods', 'Pods'), ('storage', 'Storage')):
        item = mapping(summary.get(key))
        percent = percent_from_resource(item)
        headroom = number(item.get('headroom'))
        if headroom is None and percent is not None:
            headroom = max(0.0, 100.0 - percent)
        rows.append(
            {
                'resource': label,
                'current_percent': percent,
                'headroom_percent': headroom,
                'status': first(mapping(item.get('status')), 'label', default=first(item, 'status_label', default='Not Available')),
            }
        )
    return rows


def _forecast_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sequence(mapping(payload.get('forecast_payload')).get('items')):
        rows.append(
            {
                'resource': text(item.get('key'), 'Unknown').title(),
                'current_percent': number(first(item, 'current_percent', 'historical_percent', 'current')),
                'projected_percent': number(first(item, 'projected_percent', 'forecast_percent')),
                'signal_quality': first(item, 'signal_quality', 'confidence', default='Not Available'),
                'threshold_eta': first(
                    mapping(item.get('warning_eta')),
                    'label',
                    default=first(item, 'threshold_eta', default='Not Available'),
                ),
            }
        )
    return rows


def prepare_capacity(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    rows = _capacity_rows(payload)
    metrics = tuple(metric_value(spec, row['current_percent']) for spec, row in zip(profile.metric_specs, rows, strict=True))
    tables: list[AnalyticsTableData] = [
        table('Analysis', 'Capacity & Headroom', 'Current committed capacity pressure and remaining headroom by resource.', RESOURCE_COLUMNS, rows)
    ]
    forecast_rows = _forecast_rows(payload)
    if forecast_rows:
        tables.append(
            table(
                'Forecast',
                'Capacity Forecast',
                'Committed projections supplied by the analytics worker. Excel does not calculate forecasts.',
                (
                    column('resource', 'Resource', 'Forecast resource.', width=18),
                    column('current_percent', 'Current %', 'Current committed percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    column('projected_percent', 'Projected %', 'Committed projected percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    column('signal_quality', 'Signal Quality', 'Committed forecast evidence quality.', width=18),
                    column('threshold_eta', 'Threshold ETA', 'Committed threshold timing when available.', width=20),
                ),
                forecast_rows,
            )
        )
    append_recommendations(tables, payload)
    chart_rows = tuple({'category': row['resource'], 'value': row['current_percent']} for row in rows if row['current_percent'] is not None)
    chart = None
    if chart_rows:
        chart = AnalyticsChartData(
            title='Capacity Utilization by Resource',
            visual_type='capacity_bar',
            source_sheet='Analysis',
            rows=chart_rows,
            series=(AnalyticsChartSeries('value', 'Utilization', '0.0', '%'),),
            value_axis_title='Utilization (%)',
        )
    return AnalyticsWorkbookData(profile, context, metrics, leading_percent_readout(metrics, 'capacity'), tuple(tables), chart)
