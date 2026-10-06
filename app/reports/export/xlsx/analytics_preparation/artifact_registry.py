from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    column,
    first,
    integer,
    mapping,
    metric_value,
    sequence,
    table,
)
from app.reports.export.xlsx.analytics_schema import (
    AnalyticsChartData,
    AnalyticsChartSeries,
    AnalyticsExportContext,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)


def prepare_artifact_registry(
    payload: Mapping[str, Any],
    context: AnalyticsExportContext,
    profile: AnalyticsWorkbookProfile,
) -> AnalyticsWorkbookData:
    summary = mapping(payload.get('summary'))
    values = (
        integer(summary.get('projects')) or 0,
        integer(summary.get('repositories')) or 0,
        integer(summary.get('artifacts')) or 0,
        first(summary, 'storage', default='0 B'),
    )
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))

    capacity = mapping(payload.get('artifact_registry_capacity_usage'))
    security = mapping(payload.get('artifact_registry_security_posture'))
    runtime = mapping(payload.get('artifact_registry_runtime_usage'))
    governance = mapping(payload.get('artifact_registry_governance_posture'))
    analysis_rows = [
        {'dimension': 'Storage', 'value': first(summary, 'storage', default='0 B')},
        {'dimension': 'Scan Coverage', 'value': first(security, 'scan_coverage', default='Not Available')},
        {'dimension': 'Critical Findings', 'value': integer(security.get('critical_findings')) or 0},
        {'dimension': 'Runtime Bindings', 'value': integer(runtime.get('bindings')) or 0},
        {
            'dimension': 'Governance Collection',
            'value': first(governance, 'collection_status', default='Not Collected'),
        },
        {
            'dimension': 'Growth / Day',
            'value': first(mapping(capacity.get('growth')), 'size_growth_display', default='Not Available'),
        },
    ]
    tables = [
        table(
            'Analysis',
            'Artifact Registry Operational Analysis',
            'Committed Registry capacity, security, runtime, and governance evidence.',
            (
                column('dimension', 'Dimension', 'Operational evidence dimension.', width=30),
                column('value', 'Value', 'Committed value at report cut-off.', width=34),
            ),
            analysis_rows,
        )
    ]

    consumers = [
        {
            'project': first(item, 'project_name', 'name', default='Registry Project'),
            'usage': first(item, 'usage_display', 'usage', default='Not Available'),
            'utilization': first(item, 'utilization_display', 'utilization_percent', default='Not Available'),
            'days_to_quota': first(item, 'days_to_quota_display', 'days_to_quota', default='Not Available'),
        }
        for item in sequence(payload.get('top_consumers'))
    ]
    if consumers:
        tables.append(
            table(
                'Top Consumers',
                'Registry Top Consumers',
                'Committed project consumption and quota-pressure evidence.',
                (
                    column('project', 'Project', 'Registry project identity.', width=38),
                    column('usage', 'Usage', 'Committed project usage.', width=20),
                    column('utilization', 'Utilization', 'Quota utilization when available.', width=18),
                    column('days_to_quota', 'Days to Quota', 'Forecast threshold timing when available.', width=18),
                ),
                consumers,
            )
        )

    alerts = [
        {
            'name': first(item, 'name', default='KAORI Alert Case'),
            'severity': first(item, 'severity', default='Info'),
            'state': first(item, 'state', default='Active'),
            'summary': first(item, 'summary', default='Not Available'),
        }
        for item in sequence(payload.get('alerts'))
    ]
    if alerts:
        tables.append(
            table(
                'Alerts & Anomalies',
                'Registry Alert Intelligence',
                'Active KAORI Alert Intelligence cases for the selected Registry integration.',
                (
                    column('name', 'Alert', 'Alert case identity.', width=34),
                    column('severity', 'Severity', 'Operational severity.', width=14),
                    column('state', 'State', 'Current workflow/source state.', width=18),
                    column('summary', 'Summary', 'Committed alert interpretation.', width=52),
                ),
                alerts,
            )
        )

    chart_rows = tuple({'category': row['project'], 'value': index} for index, row in enumerate(consumers[:8], start=1))
    chart = (
        AnalyticsChartData(
            title='Registry Top Consumer Order',
            visual_type='ranked_bar',
            source_sheet='Top Consumers',
            rows=chart_rows,
            series=(AnalyticsChartSeries('value', 'Rank', '#,##0', None),),
            value_axis_title='Rank',
            total_value=float(len(chart_rows)),
        )
        if chart_rows
        else None
    )
    readout = (
        f'{consumers[0]["project"]} is the leading committed consumer in the current Registry scope.'
        if consumers
        else 'No committed consumer ranking is available for the selected Registry integration.'
    )
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)
