from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    clean_unit,
    column,
    first,
    mapping,
    metric_value,
    normalized_consumer_value,
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


def _consumer_identity(item: Mapping[str, Any]) -> str:
    return text(first(mapping(item.get('identity')), 'primary', default=first(item, 'name', 'pod', 'workload')))


def _consumer_unit(item: Mapping[str, Any]) -> str:
    explicit = clean_unit(item.get('unit'))
    if explicit:
        return explicit
    display = str(first(item, 'current_display', 'display_value', 'current_usage', default='') or '').strip()
    if not display:
        return ''
    tokens = display.split()
    return clean_unit(' '.join(tokens[1:])) if len(tokens) > 1 else ''


def _normalize_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    consumer = mapping(payload.get('consumer_payload'))
    rows: list[dict[str, Any]] = []
    for item in sequence(consumer.get('all_rows') or consumer.get('rows')):
        resource = text(first(item, 'resource_type', 'resource', 'metric'), 'Unknown').title()
        source_value = number(first(item, 'current_usage', 'value', 'percent'))
        display_value = first(item, 'current_display', 'display_value', default=source_value)
        unit = _consumer_unit(item)
        display_numeric = normalized_consumer_value(
            resource=resource,
            raw_value=source_value,
            display_value=display_value,
            unit=unit,
        )
        rows.append(
            {
                'resource': resource,
                'namespace': first(item, 'namespace', default='Not Available'),
                'consumer': _consumer_identity(item),
                'value': display_numeric,
                'source_value': source_value,
                'display_numeric': display_numeric,
                'display_value': display_value,
                'unit': unit or 'Not Available',
                'status': first(mapping(item.get('risk')), 'label', default=first(item, 'status', default='Not Available')),
            }
        )
    return rows


def _ranked_rows(rows: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    preferred = next((resource for resource in ('Memory', 'CPU') if any(row['resource'] == resource for row in rows)), None)
    if preferred is None:
        preferred = next((str(row['resource']) for row in rows), None)
    ranked = [row for row in rows if row['resource'] == preferred and row['display_numeric'] is not None]
    ranked.sort(key=lambda row: float(row['display_numeric']), reverse=True)
    return preferred, ranked


def _chart(preferred: str | None, ranked: list[dict[str, Any]]) -> AnalyticsChartData | None:
    chart_rows = tuple({'category': row['consumer'], 'value': row['display_numeric']} for row in ranked[:8])
    if not chart_rows:
        return None
    unit = clean_unit(ranked[0].get('unit')) if ranked else ''
    total_value = sum(float(row['display_numeric']) for row in ranked if row['display_numeric'] is not None)
    return AnalyticsChartData(
        title=f'Top {preferred} Consumers',
        visual_type='ranked_bar',
        source_sheet='Top Consumers',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', preferred or 'Value', '#,##0.00', unit or None),),
        value_axis_title=f'{preferred} ({unit})' if unit and unit != 'Not Available' else preferred,
        total_value=total_value or None,
    )


def prepare_top_consumers(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    rows = _normalize_rows(payload)
    cpu_count = sum(1 for row in rows if str(row['resource']).casefold() == 'cpu')
    memory_count = sum(1 for row in rows if str(row['resource']).casefold() == 'memory')
    namespaces = len({text(row['namespace']) for row in rows if row['namespace'] not in (None, '', 'Not Available')})
    values = (len(rows), cpu_count, memory_count, namespaces)
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    tables: list[AnalyticsTableData] = []
    if rows:
        tables.append(
            table(
                'Top Consumers',
                'Top Consumers',
                'Committed consumer ranking evidence normalized to the published display unit for analysis.',
                (
                    column('resource', 'Resource', 'Resource signal.', width=14),
                    column('namespace', 'Namespace', 'Namespace identity.', width=28),
                    column('consumer', 'Consumer', 'Pod, workload, or resource identity.', width=44),
                    column('value', 'Value', 'Committed numeric value normalized to the published display unit.', data_type='number', number_format='#,##0.00', width=18),
                    column('unit', 'Unit', 'Published resource-specific unit.', width=12),
                    column('status', 'Status', 'Committed risk or review state.', width=18),
                ),
                rows,
            )
        )
    preferred, ranked = _ranked_rows(rows)
    if ranked:
        readout = f'{ranked[0]["consumer"]} is the leading displayed {preferred} consumer at {text(ranked[0]["display_value"], str(ranked[0]["value"]))}.'
    else:
        readout = 'No committed consumer ranking evidence is available for the selected reporting boundary.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), _chart(preferred, ranked))
