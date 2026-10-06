from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
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


def _breakdown_rows(persistent: Mapping[str, Any], filesystem_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, raw_rows in (
        ('PV', sequence(persistent.get('pv_all_rows') or persistent.get('pv_rows'))),
        ('PVC', sequence(persistent.get('pvc_all_rows') or persistent.get('pvc_rows'))),
        ('Filesystem', filesystem_rows),
    ):
        for item in raw_rows:
            identity = mapping(item.get('identity'))
            rows.append(
                {
                    'type': kind,
                    'identity': first(
                        identity,
                        'primary',
                        default=first(
                            item,
                            'name',
                            'persistent_volume',
                            'persistent_volume_claim',
                            'mountpoint',
                            default='Not Available',
                        ),
                    ),
                    'namespace': first(item, 'namespace', default='Cluster'),
                    'capacity': first(item, 'capacity_display', 'capacity', 'size', default='Not Available'),
                    'used': first(item, 'used_display', 'used', 'usage_display', default='Not Available'),
                    'free': first(item, 'free_display', 'free', 'available_display', default='Not Available'),
                    'utilization_percent': number(first(item, 'used_percent', 'utilization_percent', 'percent')),
                    'status': first(
                        mapping(item.get('risk')),
                        'label',
                        default=first(item, 'status', 'phase', default='Not Available'),
                    ),
                }
            )
    return rows


def prepare_storage(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    storage = mapping(payload.get('storage_summary'))
    persistent = mapping(storage.get('persistent_storage'))
    pv = mapping(persistent.get('pv'))
    pvc = mapping(persistent.get('pvc'))
    filesystem = mapping(storage.get('node_filesystem'))
    filesystem_rows = sequence(filesystem.get('all_rows') or filesystem.get('rows'))
    pvc_util = number(first(pvc, 'used_percent', 'utilization_percent'))
    values = (pvc_util, integer(pv.get('count')), integer(pvc.get('count')), len(filesystem_rows))
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    analysis_rows = [
        {
            'metric': 'PV Capacity',
            'value': first(pv, 'capacity', default='Not Available'),
            'status': 'Committed' if pv else 'Not Available',
        },
        {
            'metric': 'Observed Claim Usage',
            'value': first(pv, 'observed_claim_usage', default='Not Available'),
            'status': 'Committed' if pv else 'Not Available',
        },
        {
            'metric': 'PVC Used',
            'value': first(pvc, 'used', default='Not Available'),
            'status': 'Committed' if pvc else 'Not Available',
        },
        {
            'metric': 'PVC Free',
            'value': first(pvc, 'free', default='Not Available'),
            'status': 'Committed' if pvc else 'Not Available',
        },
    ]
    tables: list[AnalyticsTableData] = [
        table(
            'Analysis',
            'Storage Capacity Summary',
            'Committed persistent-storage capacity and usage evidence.',
            (
                column('metric', 'Metric', 'Storage evidence metric.', width=30),
                column('value', 'Value', 'Committed display value from analytics.', width=24),
                column('status', 'Evidence State', 'Availability of the evidence.', width=20),
            ),
            analysis_rows,
        )
    ]
    breakdown = _breakdown_rows(persistent, filesystem_rows)
    if breakdown:
        tables.append(
            table(
                'Breakdown',
                'Storage Evidence Breakdown',
                'Filesystem, PV, and PVC evidence normalized for review.',
                (
                    column('type', 'Type', 'Storage evidence type.', width=14),
                    column('identity', 'Identity', 'Storage resource identity.', width=40),
                    column('namespace', 'Namespace', 'Namespace or cluster scope.', width=26),
                    column('capacity', 'Capacity', 'Committed capacity.', width=18),
                    column('used', 'Used', 'Committed used capacity.', width=18),
                    column('free', 'Free', 'Committed free capacity.', width=18),
                    column(
                        'utilization_percent',
                        'Utilization %',
                        'Committed utilization percentage.',
                        data_type='percent',
                        number_format='0.0"%"',
                        width=16,
                    ),
                    column('status', 'Status', 'Lifecycle or risk label.', width=18),
                ),
                breakdown,
            )
        )
    append_recommendations(tables, payload)
    chart_rows: tuple[Mapping[str, Any], ...] = ()
    if pvc_util is not None:
        chart_rows = ({'category': 'Persistent Claims', 'value': pvc_util},)
    chart = None
    if chart_rows:
        chart = AnalyticsChartData(
            title='Persistent Claim Capacity Posture',
            visual_type='capacity_bar',
            source_sheet='Analysis',
            rows=chart_rows,
            series=(AnalyticsChartSeries('value', 'Percent', '0.0', '%'),),
            value_axis_title='Percent',
        )
    return AnalyticsWorkbookData(
        profile, context, metrics, leading_percent_readout((metrics[0],), 'storage'), tuple(tables), chart
    )
