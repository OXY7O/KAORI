from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    append_recommendations,
    column,
    first,
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


def _forecast_item_percent(item: Mapping[str, Any]) -> float | None:
    return number(first(item, 'projected_percent', 'forecast_percent', 'projected'))


def _trend_rows(item: Mapping[str, Any], resource: str) -> list[dict[str, Any]]:
    historical = sequence(item.get('historical_points'))
    projected = sequence(item.get('forecast_points'))
    rows: list[dict[str, Any]] = []
    for index in range(max(len(historical), len(projected))):
        hist = historical[index] if index < len(historical) else {}
        proj = projected[index] if index < len(projected) else {}
        rows.append(
            {
                'observation': index + 1,
                'historical_percent': number(first(hist, 'percent', 'value')),
                'forecast_percent': number(first(proj, 'percent', 'value')),
                'resource': resource,
            }
        )
    return rows


def prepare_forecast(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    forecast = mapping(payload.get('forecast_payload'))
    items = sequence(forecast.get('items'))
    by_key = {str(item.get('key') or '').casefold(): item for item in items}
    values = tuple(_forecast_item_percent(mapping(by_key.get(key))) for key in ('cpu', 'memory', 'pods', 'storage'))
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    analysis_rows = [
        {
            'resource': key.title(),
            'current_percent': number(first(item, 'current_percent', 'historical_percent', 'current')),
            'projected_percent': _forecast_item_percent(item),
            'signal_quality': first(item, 'signal_quality', 'confidence', default='Not Available'),
            'threshold_eta': first(mapping(item.get('warning_eta')), 'label', default=first(item, 'threshold_eta', default='Not Available')),
        }
        for key, item in by_key.items()
    ]
    tables: list[AnalyticsTableData] = []
    if analysis_rows:
        tables.append(
            table(
                'Analysis',
                'Forecast Summary',
                'Committed current and projected resource signals.',
                (
                    column('resource', 'Resource', 'Forecast resource.', width=18),
                    column('current_percent', 'Current %', 'Current committed percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    column('projected_percent', 'Projected %', 'Committed projected percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    column('signal_quality', 'Signal Quality', 'Committed signal quality.', width=18),
                    column('threshold_eta', 'Threshold ETA', 'Committed threshold timing.', width=20),
                ),
                analysis_rows,
            )
        )

    preferred_key = next((key for key in ('memory', 'cpu', 'pods', 'storage') if key in by_key), None)
    preferred_label = str(preferred_key).title() if preferred_key else 'Resource'
    trend_rows = _trend_rows(mapping(by_key[preferred_key]), preferred_label) if preferred_key else []
    if trend_rows:
        tables.append(
            table(
                'Trends',
                f'{preferred_label} Forecast Trend',
                'Committed historical and forecast points in source order.',
                (
                    column('observation', 'Observation', 'Source-order point.', data_type='integer', number_format='#,##0', width=14),
                    column('resource', 'Resource', 'Forecast resource.', width=16),
                    column('historical_percent', 'Historical %', 'Committed historical percentage.', data_type='percent', number_format='0.0"%"', width=16),
                    column('forecast_percent', 'Forecast %', 'Committed forecast percentage.', data_type='percent', number_format='0.0"%"', width=16),
                ),
                trend_rows,
            )
        )
    append_recommendations(tables, payload)
    chart = None
    if trend_rows:
        chart = AnalyticsChartData(
            title=f'{preferred_label} Historical & Forecast Direction',
            visual_type='line',
            source_sheet='Trends',
            rows=tuple(trend_rows),
            category_key='observation',
            series=(
                AnalyticsChartSeries('historical_percent', 'Historical', '0.0', '%'),
                AnalyticsChartSeries('forecast_percent', 'Forecast', '0.0', '%'),
            ),
            value_axis_title='Percent',
        )
    return AnalyticsWorkbookData(profile, context, metrics, leading_percent_readout(metrics, 'forecast'), tuple(tables), chart)
