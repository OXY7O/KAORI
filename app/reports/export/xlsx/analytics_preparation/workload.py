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
)
from app.reports.export.xlsx.analytics_schema import (
    AnalyticsChartData,
    AnalyticsChartSeries,
    AnalyticsExportContext,
    AnalyticsTableData,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)


def prepare_workload(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    quota = mapping(payload.get('tenant_quota_summary'))
    quota_rows = sequence(payload.get('tenant_quota_rows') or quota.get('rows'))
    mapping_rows_raw = sequence(
        payload.get('workload_mapping_rows') or mapping(payload.get('workload_mapping_payload')).get('rows')
    )
    findings = sequence(payload.get('governance_findings'))
    total = integer(quota.get('scope_total')) or len(quota_rows)
    covered = integer(quota.get('scope_covered'))
    coverage = (covered / total * 100.0) if total else None
    near_limit = integer(first(quota, 'scope_near_limit_count', 'near_limit_count', default=0))
    values = (coverage, near_limit, len(mapping_rows_raw), len(findings))
    metrics = tuple(metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))

    normalized_quota = [
        {
            'namespace': first(item, 'namespace', 'name', default='Not Available'),
            'quota_status': first(
                mapping(item.get('quota_status')), 'label', default=first(item, 'status', default='Not Available')
            ),
            'cpu': first(item, 'cpu', 'cpu_display', default='Not Available'),
            'memory': first(item, 'memory', 'memory_display', default='Not Available'),
            'pods': first(item, 'pods', 'pod_display', default='Not Available'),
        }
        for item in quota_rows
    ]
    tables: list[AnalyticsTableData] = []
    if normalized_quota:
        tables.append(
            table(
                'Analysis',
                'Tenant Quota Analysis',
                'Committed ResourceQuota coverage and posture by namespace.',
                (
                    column('namespace', 'Namespace', 'Namespace identity.', width=30),
                    column('quota_status', 'Quota Status', 'Committed quota coverage status.', width=20),
                    column('cpu', 'CPU', 'CPU quota evidence.', width=20),
                    column('memory', 'Memory', 'Memory quota evidence.', width=20),
                    column('pods', 'Pods', 'Pod quota evidence.', width=18),
                ),
                normalized_quota,
            )
        )

    normalized_mapping = [
        {
            'namespace': first(item, 'namespace', default='Not Available'),
            'workload': first(
                mapping(item.get('identity')),
                'primary',
                default=first(item, 'workload', 'name', default='Not Available'),
            ),
            'kind': first(item, 'kind', 'workload_kind', default='Not Available'),
            'requests': first(item, 'requests', 'request_display', default='Not Available'),
            'limits': first(item, 'limits', 'limit_display', default='Not Available'),
            'status': first(
                mapping(item.get('risk')), 'label', default=first(item, 'status', 'qos_class', default='Not Available')
            ),
        }
        for item in mapping_rows_raw
    ]
    if normalized_mapping:
        tables.append(
            table(
                'Breakdown',
                'Workload Resource Mapping',
                'Committed workload requests, limits, and governance posture.',
                (
                    column('namespace', 'Namespace', 'Namespace identity.', width=28),
                    column('workload', 'Workload', 'Workload identity.', width=42),
                    column('kind', 'Kind', 'Kubernetes workload kind.', width=18),
                    column('requests', 'Requests', 'Committed request evidence.', width=24),
                    column('limits', 'Limits', 'Committed limit evidence.', width=24),
                    column('status', 'Status', 'Governance or QoS evidence.', width=20),
                ),
                normalized_mapping,
            )
        )
    append_recommendations(tables, payload)

    chart_rows: tuple[Mapping[str, Any], ...] = ()
    if total:
        chart_rows = (
            {'category': 'Quota Covered', 'value': covered},
            {'category': 'Quota Not Covered', 'value': max(total - covered, 0)},
        )
    chart = None
    if chart_rows:
        chart = AnalyticsChartData(
            title='Namespace Quota Coverage',
            visual_type='composition_bar',
            source_sheet='Analysis' if normalized_quota else 'Overview',
            rows=chart_rows,
            series=(AnalyticsChartSeries('value', 'Namespaces', '#,##0'),),
            total_value=float(total) if total else None,
        )
    if coverage is None:
        readout = 'No committed tenant quota coverage denominator is available for the selected reporting boundary.'
    else:
        readout = (
            f'{coverage:.1f}% of {total:,} namespace quota records are covered in the committed analytics evidence.'
        )
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)
