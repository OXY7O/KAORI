from __future__ import annotations

from app.reports.export.xlsx.analytics_schema import (
    AnalyticsColumn,
    AnalyticsMetricSpec,
    AnalyticsWorkbookProfile,
)


def _metric(label: str, *, fmt: str = 'General', unit: str | None = None) -> AnalyticsMetricSpec:
    return AnalyticsMetricSpec(label=label, number_format=fmt, unit=unit)


def _column(
    key: str,
    label: str,
    definition: str,
    *,
    data_type: str = 'text',
    number_format: str | None = None,
    unit: str | None = None,
    width: float = 18.0,
) -> AnalyticsColumn:
    return AnalyticsColumn(
        key=key,
        label=label,
        definition=definition,
        data_type=data_type,  # type: ignore[arg-type]
        number_format=number_format,
        unit=unit,
        width=width,
    )


ANALYTICS_WORKBOOK_PROFILES: dict[str, AnalyticsWorkbookProfile] = {
    'analytics_overview': AnalyticsWorkbookProfile(
        report_type='analytics_overview',
        title='Analytics Overview',
        description='Cross-domain operational analytics posture, trends, alerts, and leading evidence.',
        metric_specs=(
            _metric('CPU Utilization', fmt='0.0"%"'),
            _metric('Memory Utilization', fmt='0.0"%"'),
            _metric('Forecast Peak', fmt='0.0"%"'),
            _metric('Active Alerts', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Trends', 'Top Consumers', 'Alerts & Anomalies', 'Recommendations'),
        primary_visual='comparison_bar',
    ),
    'resource_utilization': AnalyticsWorkbookProfile(
        report_type='resource_utilization',
        title='Resource Utilization',
        description='CPU, memory, storage, pod utilization, trends, and leading consumer evidence.',
        metric_specs=(
            _metric('CPU Utilization', fmt='0.0"%"'),
            _metric('Memory Utilization', fmt='0.0"%"'),
            _metric('Storage Utilization', fmt='0.0"%"'),
            _metric('Pod Utilization', fmt='0.0"%"'),
        ),
        sheet_names=('Analysis', 'Trends', 'Top Consumers'),
        primary_visual='line',
    ),
    'capacity_analysis': AnalyticsWorkbookProfile(
        report_type='capacity_analysis',
        title='Capacity Analysis',
        description='Worker capacity, consumption, headroom, allocation, and projected pressure evidence.',
        metric_specs=(
            _metric('CPU Usage', fmt='0.0"%"'),
            _metric('Memory Usage', fmt='0.0"%"'),
            _metric('Pod Usage', fmt='0.0"%"'),
            _metric('Storage Usage', fmt='0.0"%"'),
        ),
        sheet_names=('Analysis', 'Forecast', 'Recommendations'),
        primary_visual='capacity_bar',
    ),
    'storage_analysis': AnalyticsWorkbookProfile(
        report_type='storage_analysis',
        title='Storage Analysis',
        description='Filesystem and persistent storage capacity, usage, free space, lifecycle, and forecast evidence.',
        metric_specs=(
            _metric('PVC Utilization', fmt='0.0"%"'),
            _metric('Persistent Volumes', fmt='#,##0'),
            _metric('Persistent Claims', fmt='#,##0'),
            _metric('Filesystem Records', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Breakdown', 'Forecast', 'Recommendations'),
        primary_visual='capacity_bar',
    ),
    'workload_analysis': AnalyticsWorkbookProfile(
        report_type='workload_analysis',
        title='Workload Analysis',
        description='Tenant quota coverage, workload resource mapping, governance findings, and committed recommendations.',
        metric_specs=(
            _metric('Quota Coverage', fmt='0.0"%"'),
            _metric('Near Limit', fmt='#,##0'),
            _metric('Mapped Workloads', fmt='#,##0'),
            _metric('Governance Findings', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Breakdown', 'Recommendations'),
        primary_visual='composition_bar',
    ),
    'resource_forecast': AnalyticsWorkbookProfile(
        report_type='resource_forecast',
        title='Resource Forecast',
        description='Committed historical and forecast evidence for CPU, memory, storage, and pod growth.',
        metric_specs=(
            _metric('CPU Projection', fmt='0.0"%"'),
            _metric('Memory Projection', fmt='0.0"%"'),
            _metric('Pod Projection', fmt='0.0"%"'),
            _metric('Storage Projection', fmt='0.0"%"'),
        ),
        sheet_names=('Analysis', 'Trends', 'Recommendations'),
        primary_visual='line',
    ),
    'top_consumers': AnalyticsWorkbookProfile(
        report_type='top_consumers',
        title='Top Consumers',
        description='Ranked namespace, workload, and pod resource-consumption evidence for the selected scope.',
        metric_specs=(
            _metric('Displayed Consumers', fmt='#,##0'),
            _metric('CPU Consumers', fmt='#,##0'),
            _metric('Memory Consumers', fmt='#,##0'),
            _metric('Namespaces', fmt='#,##0'),
        ),
        sheet_names=('Top Consumers',),
        primary_visual='ranked_bar',
    ),
    'alerts_anomalies': AnalyticsWorkbookProfile(
        report_type='alerts_anomalies',
        title='Alerts & Anomalies',
        description='Committed alert severity, anomaly evidence, ownership context, and response recommendations.',
        metric_specs=(
            _metric('Active Alerts', fmt='#,##0'),
            _metric('Critical Alerts', fmt='#,##0'),
            _metric('Warning Alerts', fmt='#,##0'),
            _metric('Anomalies', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Alerts & Anomalies', 'Recommendations'),
        primary_visual='composition_bar',
    ),
    'object_storage_analysis': AnalyticsWorkbookProfile(
        report_type='object_storage_analysis',
        title='Object Storage Analysis',
        description='Capacity, usage, performance, growth, consumer concentration, and alert evidence for one Object Storage system.',
        metric_specs=(
            _metric('Capacity'),
            _metric('Usage'),
            _metric('Headroom'),
            _metric('Utilization'),
        ),
        sheet_names=('Analysis', 'Top Consumers', 'Trends', 'Alerts & Anomalies'),
        primary_visual='ranked_bar',
    ),
}

ANALYTICS_XLSX_REPORT_TYPES = frozenset(ANALYTICS_WORKBOOK_PROFILES)


def _validate_profiles() -> None:
    visual_types = {'line', 'ranked_bar', 'composition_bar', 'capacity_bar', 'comparison_bar'}
    for report_type, profile in ANALYTICS_WORKBOOK_PROFILES.items():
        if profile.report_type != report_type:
            raise ValueError(f'Analytics XLSX profile key {report_type!r} does not match profile report type.')
        if len(profile.metric_specs) != 4:
            raise ValueError(f'Analytics XLSX profile {report_type!r} must declare exactly four overview metrics.')
        if not profile.sheet_names:
            raise ValueError(f'Analytics XLSX profile {report_type!r} must declare category-owned sheet names.')
        if profile.primary_visual not in visual_types:
            raise ValueError(f'Analytics XLSX profile {report_type!r} has unsupported primary visual.')
        if len(set(profile.sheet_names)) != len(profile.sheet_names):
            raise ValueError(f'Analytics XLSX profile {report_type!r} declares duplicate sheet names.')


_validate_profiles()
