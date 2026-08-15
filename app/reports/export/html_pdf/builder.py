from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.reports.catalog import get_report_type_spec
from app.reports.export.constants import (
    ANALYTICS_OVERVIEW_SECTION_KEYS,
    ANALYTICS_REPORT_RECOMMENDATIONS,
    DEFAULT_RECOMMENDATIONS,
    SECTION_LABELS,
)
from app.reports.export.formatting import format_period
from app.reports.export.html_pdf.alerts_anomalies import build_alerts_anomalies_presentation
from app.reports.export.html_pdf.analytics_overview import build_analytics_overview_presentation
from app.reports.export.html_pdf.builder_context import ReportDocumentContext, finalize_report_document
from app.reports.export.html_pdf.capacity_analysis import build_capacity_analysis_presentation
from app.reports.export.html_pdf.charts import build_alert_severity_chart, build_forecast_chart
from app.reports.export.html_pdf.document import (
    ReportDocument,
    ReportFinding,
    ReportMetric,
    ReportSection,
)
from app.reports.export.html_pdf.forecast_analysis import build_forecast_analysis_presentation
from app.reports.export.html_pdf.normalization import (
    find_first_path,
    findings_from_value,
    humanize_key,
    metrics_from_mapping,
    sanitize_error_message,
    sanitize_text,
    tables_from_value,
    tone_from_value,
)
from app.reports.export.html_pdf.resource_utilization import build_resource_utilization_presentation
from app.reports.export.html_pdf.storage_analysis import build_storage_analysis_presentation
from app.reports.export.html_pdf.top_consumers_analysis import build_top_consumers_analysis_presentation
from app.reports.export.html_pdf.workload_analysis import build_workload_analysis_presentation
from app.reports.reference import build_report_reference
from app.reports.scope import OBJECT_STORAGE_SYSTEM_ASSET_TYPE, resolve_report_scope

_SECTION_SOURCE_PATHS: dict[str, tuple[str, ...]] = {
    'analytics_summary': ('health_summary', 'summary'),
    'resource_snapshot': ('resource_snapshot', 'summary_table', 'summary'),
    'risk_overview': ('risk_assessment', 'risk_summary', 'health_summary', 'storage_summary'),
    'cpu_utilization': ('summary.cpu', 'summary_table.cpu', 'cpu'),
    'memory_utilization': ('summary.memory', 'summary_table.memory', 'memory'),
    'storage_utilization': ('summary.storage', 'summary_table.storage', 'storage'),
    'pod_utilization': ('summary.pods', 'summary_table.pods', 'pods'),
    'node_resource_detail': ('cluster_info', 'summary'),
    'worker_capacity_summary': ('worker_capacity_summary', 'cluster_info'),
    'resource_allocation_headroom': ('allocation_summary', 'capacity_summary'),
    'capacity_pressure_risk': ('risk_summary', 'governance_findings'),
    'filesystem_summary': ('storage_summary.node_filesystem', 'storage_summary.filesystem_summary'),
    'persistent_volume_summary': ('storage_summary.persistent_storage.pv', 'storage_summary.pv_rows'),
    'persistent_volume_claims': ('storage_summary.persistent_storage.pvc', 'storage_summary.pvc_rows'),
    'storage_risk': ('storage_summary.risk_summary', 'storage_summary'),
    'tenant_quota_summary': ('tenant_quota_summary', 'tenant_quota_rows'),
    'request_limit_coverage': ('workload_mapping_payload.summary', 'workload_mapping_rows'),
    'workload_resource_mapping': ('workload_mapping_rows', 'workload_mapping_payload.rows'),
    'governance_findings': ('governance_findings',),
    'forecast_summary': ('forecast_payload.summary', 'forecast_payload'),
    'forecast_risk_summary': ('forecast_payload.summary',),
    'resource_trend_summary': ('forecast_payload.items',),
    'cpu_forecast': ('forecast_payload.items',),
    'memory_forecast': ('forecast_payload.items',),
    'storage_forecast': ('forecast_payload.items',),
    'pod_forecast': ('forecast_payload.items',),
    'capacity_projection': ('forecast_payload.items',),
    'forecast_projection': ('forecast_payload.items',),
    'threshold_eta': ('forecast_payload.items',),
    'top_namespace_consumers': ('consumer_payload.rows', 'consumer_payload'),
    'top_workload_consumers': ('consumer_payload.rows',),
    'top_pod_consumers': ('consumer_payload.rows',),
    'resource_hotspots': ('consumer_payload.hotspots', 'consumer_payload.rows', 'consumer_payload.summary'),
    'active_alerts': ('alerts',),
    'alert_severity_summary': ('summary', 'alerts'),
    'source_health': ('source_health', 'source_status', 'integration_status'),
    'routing_grouping': ('routing_summary',),
    'silence_inhibition': ('silence_summary', 'inhibition_summary'),
    'ownership_runbook': ('ownership_summary',),
    'incident_readiness': ('incident_readiness',),
    'anomaly_context': ('anomalies',),
    'affected_resources': ('alerts', 'anomalies'),
    'object_storage_capacity_usage': ('capacity_usage', 'summary'),
    'object_storage_bucket_distribution': ('bucket_rows',),
    'object_storage_quota_headroom': ('bucket_analysis', 'capacity_usage'),
    'object_storage_performance': ('performance',),
    'object_storage_forecast': ('forecast_display', 'forecast_materialization'),
    'object_storage_top_consumers': ('top_consumers',),
    'object_storage_risk_findings': (
        'risk_findings',
        'signals',
        'signal_posture',
        'operational_posture',
        'alert_posture',
    ),
    'methodology_evidence_boundary': ('evidence_boundary',),
}

_SECTION_DESCRIPTIONS: dict[str, str] = {
    'executive_summary': 'Management-oriented summary of scope, source readiness, data posture, and the most important findings.',
    'operational_recommendations': 'Prioritized actions derived from the selected report data and KAORI operational guidance.',
    'resource_snapshot': 'Current resource posture for the selected reporting scope.',
    'risk_overview': 'Conditions that require attention, including degraded sources, capacity pressure, and active risk signals.',
    'resource_allocation_headroom': 'Capacity allocation, current consumption, and remaining schedulable headroom.',
    'capacity_pressure_risk': 'Capacity pressure and governance conditions that may affect workload placement or availability.',
    'forecast_summary': 'Projected resource growth, threshold exposure, and historical signal quality for the selected horizon.',
    'alert_severity_summary': 'Distribution of active alert signals by operational severity.',
    'source_health': 'Connectivity and readiness posture of the alert and analytics source integrations.',
    'object_storage_capacity_usage': 'Committed capacity, usage, utilization, and remaining headroom for the selected Object Storage system.',
    'object_storage_bucket_distribution': 'Bucket and container distribution derived from the latest committed Object Storage inventory snapshot.',
    'object_storage_quota_headroom': 'Quota evidence, quota utilization, and remaining headroom for governed Object Storage capacity review.',
    'object_storage_performance': 'Validated request, error, traffic, waiting, and node availability evidence for the selected reporting period.',
    'object_storage_forecast': 'Worker-materialized Object Storage forecast evidence and its current publication readiness.',
    'object_storage_top_consumers': 'Highest retained Object Storage consumers in the selected committed inventory boundary.',
    'object_storage_risk_findings': 'Operational signals, alert posture, and risk conditions requiring accountable review.',
    'methodology_evidence_boundary': 'Authoritative source ownership, data cut-off, and limitations used to build this governed publication.',
}


def _build_document_context(report: Any, payload: Mapping[str, Any]) -> ReportDocumentContext:
    generated_at = datetime.now(UTC)
    selected_sections = list(report.sections_as_list())
    if report.report_type == 'analytics_overview':
        selected_sections = list(ANALYTICS_OVERVIEW_SECTION_KEYS)
    if not selected_sections:
        selected_sections = ['executive_summary', 'operational_recommendations']

    sections: list[ReportSection] = []
    if payload.get('_error'):
        sections.append(_build_error_section(payload, number=1))
    else:
        for number, section_key in enumerate(selected_sections, start=1):
            sections.append(_build_section(report, payload, section_key, number))

    generated_by = (
        getattr(report, 'generated_by_display_name_snapshot', None)
        or getattr(report, 'generated_by_username_snapshot', None)
        or 'KAORI Automation'
    )
    report_type_spec = get_report_type_spec(report.report_type)
    overall_posture, overall_tone = _derive_overall_posture(payload)
    return ReportDocumentContext(
        generated_at=generated_at,
        selected_sections=selected_sections,
        source_metrics=_build_source_metrics(report, payload),
        overall_posture=overall_posture,
        overall_tone=overall_tone,
        sections=sections,
        generated_by_label=sanitize_text(generated_by),
        cluster_scope=_cluster_scope(report, payload),
        namespace_scope=_secondary_scope(report),
        internal_report_id=str(getattr(report, 'id', '-')),
        report_id=build_report_reference(report, generated_at=generated_at),
        report_name=sanitize_text(getattr(report, 'name', None), fallback='KAORI Operational Report'),
        report_type_spec=report_type_spec,
        report_type_label=report_type_spec.label.removesuffix(' Report'),
        period_label=_report_period_label(report),
        generated_at_label=generated_at.strftime('%d %b %Y %H:%M UTC'),
        data_cutoff=_derive_data_cutoff(payload, generated_at),
    )


def build_report_document(
    report: Any,
    payload: Mapping[str, Any],
    *,
    classification: str = 'Internal',
    retention_days: int = 90,
) -> ReportDocument:
    context = _build_document_context(report, payload)
    template_name = 'reports/pdf/analytics_unavailable.html'
    presentation: dict[str, Any] = {}
    if payload.get('_error'):
        if report.report_type == 'object_storage_analysis':
            template_name = 'reports/pdf/object_storage_analysis.html'
            presentation = {
                'report_id': context.report_id,
                'classification': classification,
                'page_count': 1 + len(context.sections),
                'scope_value': context.cluster_scope,
                'source_label': 'Object Storage Evidence Unavailable',
                'metrics_contract': 'Generation Limited',
            }
        else:
            presentation = _build_unavailable_presentation(
                report,
                payload,
                report_reference=context.report_id,
                report_name=context.report_name,
                report_type_label=context.report_type_label,
                cluster_scope=context.cluster_scope,
                namespace_scope=context.namespace_scope,
                period_label=context.period_label,
                data_cutoff=context.data_cutoff,
                generated_at=context.generated_at_label,
                generated_by=context.generated_by_label,
                classification=classification,
            )
    elif report.report_type == 'analytics_overview':
        template_name = 'reports/pdf/analytics_overview.html'
        presentation = build_analytics_overview_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
            overall_posture=context.overall_posture,
            overall_tone=context.overall_tone,
        )
    elif report.report_type == 'resource_utilization':
        template_name = 'reports/pdf/resource_utilization.html'
        presentation = build_resource_utilization_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'capacity_analysis':
        template_name = 'reports/pdf/capacity_analysis.html'
        presentation = build_capacity_analysis_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'storage_analysis':
        template_name = 'reports/pdf/storage_analysis.html'
        presentation = build_storage_analysis_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'resource_forecast':
        template_name = 'reports/pdf/forecast_analysis.html'
        presentation = build_forecast_analysis_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'workload_analysis':
        template_name = 'reports/pdf/workload_analysis.html'
        presentation = build_workload_analysis_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'top_consumers':
        template_name = 'reports/pdf/top_consumers_analysis.html'
        presentation = build_top_consumers_analysis_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'alerts_anomalies':
        template_name = 'reports/pdf/alerts_anomalies.html'
        presentation = build_alerts_anomalies_presentation(
            report,
            payload,
            report_id=context.report_id,
            report_name=context.report_name,
            cluster_scope=context.cluster_scope,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
            generated_at=context.generated_at_label,
            generated_by=context.generated_by_label,
            classification=classification,
        )
    elif report.report_type == 'object_storage_analysis':
        template_name = 'reports/pdf/object_storage_analysis.html'
        metrics_source = payload.get('metrics_source') if isinstance(payload.get('metrics_source'), Mapping) else {}
        metrics_readiness = (
            payload.get('metrics_readiness') if isinstance(payload.get('metrics_readiness'), Mapping) else {}
        )
        presentation = {
            'report_id': context.report_id,
            'classification': classification,
            'page_count': 1 + len(context.sections),
            'scope_value': context.cluster_scope,
            'source_label': sanitize_text(
                metrics_source.get('provider_label') or metrics_source.get('label'),
                fallback='Object Storage Evidence',
            ),
            'metrics_contract': sanitize_text(
                metrics_readiness.get('label') or metrics_readiness.get('status'),
                fallback='Evidence Boundary Recorded',
            ),
        }

    return finalize_report_document(
        report,
        context,
        template_name=template_name,
        presentation=presentation,
        classification=classification,
        retention_days=retention_days,
    )


def _build_section(report: Any, payload: Mapping[str, Any], section_key: str, number: int) -> ReportSection:
    title = SECTION_LABELS.get(section_key, humanize_key(section_key))
    description = _SECTION_DESCRIPTIONS.get(
        section_key,
        f'Operational evidence and interpretation for {title.lower()}.',
    )

    if section_key == 'executive_summary':
        return _build_executive_summary(report, payload, number)

    if section_key == 'operational_recommendations':
        return _build_recommendations_section(report, payload, number)

    value = find_first_path(payload, _SECTION_SOURCE_PATHS.get(section_key, (section_key,)))
    if value is None:
        value = {}

    forecast_resource_keys = {
        'cpu_forecast': 'cpu',
        'memory_forecast': 'memory',
        'storage_forecast': 'storage',
        'pod_forecast': 'pods',
    }
    resource_key = forecast_resource_keys.get(section_key)
    if resource_key and isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        value = [
            item for item in value if isinstance(item, Mapping) and str(item.get('key', '')).lower() == resource_key
        ]

    metrics = metrics_from_mapping(value) if isinstance(value, Mapping) else ()
    tables = tables_from_value(title, value)
    findings = (
        findings_from_value(value)
        if not tables
        or section_key
        in {
            'risk_overview',
            'capacity_pressure_risk',
            'governance_findings',
            'resource_hotspots',
            'object_storage_risk_findings',
        }
        else ()
    )

    chart_svg = ''
    if report.report_type == 'resource_forecast' and section_key in {
        'forecast_summary',
        'forecast_risk_summary',
        'resource_trend_summary',
        'cpu_forecast',
        'memory_forecast',
        'storage_forecast',
        'pod_forecast',
        'capacity_projection',
        'forecast_projection',
    }:
        chart_svg = build_forecast_chart(payload)
    elif report.report_type == 'alerts_anomalies' and section_key == 'alert_severity_summary':
        chart_svg = build_alert_severity_chart(payload)

    status_label, status_tone = _section_status(value)
    note = ''
    if not metrics and not tables and not findings and not chart_svg:
        note = 'No structured evidence was returned for this section in the current reporting snapshot.'

    return ReportSection(
        key=section_key,
        number=number,
        title=title,
        description=description,
        status_label=status_label,
        status_tone=status_tone,
        metrics=metrics,
        findings=findings,
        tables=tables,
        chart_svg=chart_svg,
        note=note,
        page_orientation='landscape' if any(len(table.columns) > 6 for table in tables) else 'portrait',
    )


def _build_executive_summary(report: Any, payload: Mapping[str, Any], number: int) -> ReportSection:
    scope_asset_type = str(getattr(report, 'scope_asset_type', '') or '')
    metrics: list[ReportMetric] = [
        ReportMetric(
            'Object Storage System' if scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE else 'Cluster Scope',
            _cluster_scope(report, payload),
            tone='info',
        ),
        ReportMetric('Reporting Period', _report_period_label(report)),
    ]
    if scope_asset_type != OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        metrics.insert(
            1,
            ReportMetric(
                'Namespace Scope',
                sanitize_text(getattr(report, 'namespace', None), fallback='All Namespaces'),
            ),
        )

    selected_asset = (
        payload.get('selected_system')
        or payload.get('system')
        or payload.get('cluster')
        or payload.get('selected_cluster')
    )
    if isinstance(selected_asset, Mapping):
        environment = selected_asset.get('environment')
        if environment:
            metrics.append(ReportMetric('Environment', sanitize_text(environment), tone='info'))

    for status_key in ('inventory_status', 'prometheus_status', 'source_status', 'integration_status'):
        status = payload.get(status_key)
        if isinstance(status, Mapping):
            label = status.get('label') or status.get('status_label') or status.get('status')
            if label:
                metrics.append(
                    ReportMetric(
                        humanize_key(status_key),
                        sanitize_text(label),
                        sanitize_text(status.get('description') or status.get('message'), fallback='')[:140],
                        tone_from_value(label),
                    )
                )
                break

    summary_value = payload.get('summary') or payload.get('health_summary') or payload.get('forecast_payload')
    summary_metrics = (
        metrics_from_mapping(summary_value, limit=max(0, 8 - len(metrics)))
        if isinstance(summary_value, Mapping)
        else ()
    )
    metrics.extend(summary_metrics)

    findings: list[ReportFinding] = []
    for key in ('risk_assessment', 'governance_findings', 'source_health', 'incident_readiness'):
        value = payload.get(key)
        if value:
            findings.extend(findings_from_value(value, limit=3))
        if len(findings) >= 5:
            break

    posture, tone = _derive_overall_posture(payload)
    return ReportSection(
        key='executive_summary',
        number=number,
        title='Executive Summary',
        description='Management-oriented summary of the selected scope, source readiness, and the findings that require attention.',
        status_label=posture,
        status_tone=tone,
        metrics=tuple(metrics[:8]),
        findings=tuple(findings[:5]),
    )


def _build_recommendations_section(report: Any, payload: Mapping[str, Any], number: int) -> ReportSection:
    recommendation_value = payload.get('actionable_recommendations') or payload.get('recommendations')
    forecast_payload = payload.get('forecast_payload')
    if not recommendation_value and isinstance(forecast_payload, Mapping):
        recommendation_value = forecast_payload.get('actionable_recommendations')
    if not recommendation_value:
        recommendation_value = ANALYTICS_REPORT_RECOMMENDATIONS.get(report.report_type, DEFAULT_RECOMMENDATIONS)

    findings = findings_from_value(recommendation_value, limit=12)
    return ReportSection(
        key='operational_recommendations',
        number=number,
        title='Operational Recommendations',
        description='Prioritized follow-up actions based on the evidence available in this report.',
        status_label=f'{len(findings)} Actions',
        status_tone='info' if findings else 'neutral',
        findings=findings,
        note='Recommendation ownership and due dates should be assigned in the operational workflow before closure.',
    )


def _build_error_section(payload: Mapping[str, Any], *, number: int) -> ReportSection:
    return ReportSection(
        key='data_unavailable',
        number=number,
        title='Report Data Unavailable',
        description='KAORI could not collect the required report payload at generation time.',
        status_label='Limited',
        status_tone='warning',
        findings=(
            ReportFinding(
                title='Source Data Was Not Available',
                description=sanitize_error_message(payload.get('_error')),
                tone='warning',
            ),
            ReportFinding(
                title='Recommended Next Step',
                description='Review integration readiness, allow automatic recovery to complete, and regenerate the report.',
                tone='info',
            ),
        ),
    )


def _report_period_label(report: Any) -> str:
    return format_period(getattr(report, 'period', '30d'))


def _cluster_scope(report: Any, payload: Mapping[str, Any]) -> str:
    selected_asset = (
        payload.get('selected_system')
        or payload.get('system')
        or payload.get('cluster')
        or payload.get('selected_cluster')
    )
    if isinstance(selected_asset, Mapping):
        name = selected_asset.get('name')
        identifier = selected_asset.get('id')
        if name:
            return sanitize_text(name)
        if identifier:
            return sanitize_text(identifier)

    snapshot = getattr(report, 'scope_asset_label_snapshot', None)
    if snapshot:
        return sanitize_text(snapshot)
    scope = resolve_report_scope(report)
    if scope is not None:
        return sanitize_text(scope.label)
    return sanitize_text(getattr(report, 'cluster_id', None), fallback='Selected Asset Unavailable')


def _secondary_scope(report: Any) -> str:
    scope_asset_type = str(getattr(report, 'scope_asset_type', '') or '')
    if scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        return 'System Scope'
    return sanitize_text(getattr(report, 'namespace', None), fallback='All Namespaces')


def _derive_data_cutoff(payload: Mapping[str, Any], generated_at: datetime) -> str:
    for key in ('data_cutoff', 'last_analyzed_at', 'collected_at', 'updated_at', 'generated_at'):
        value = payload.get(key)
        if value:
            return sanitize_text(value)
    return generated_at.strftime('%d %b %Y %H:%M UTC')


def _build_unavailable_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_reference: str,
    report_name: str,
    report_type_label: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    error_message = sanitize_error_message(payload.get('_error'))
    return {
        'report_id': report_reference,
        'report_name': report_name,
        'report_type_label': report_type_label,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'page_count': 3,
        'cover': {
            'purpose': 'Record the selected report boundary and the source limitation without inventing analytical conclusions.',
            'context': 'The required source payload was unavailable at generation time. Missing evidence remains explicit and is not converted to zero, healthy, stable, or clear.',
        },
        'availability': {
            'status': 'Source Unavailable',
            'tone': 'warning',
            'summary': error_message or 'KAORI could not collect the required report payload at generation time.',
            'findings': (
                {
                    'ref': 'A1',
                    'title': 'Required Evidence Was Not Available',
                    'description': 'The renderer received an explicit source limitation and excluded conclusions that require the missing evidence.',
                },
                {
                    'ref': 'A2',
                    'title': 'Previous Evidence Was Not Reused Silently',
                    'description': 'This artifact does not substitute stale, unrelated, or cross-cluster evidence for the selected report boundary.',
                },
            ),
        },
        'recovery': {
            'steps': (
                'Review integration readiness and the related JobExecution record.',
                'Restore the required source, permission, or worker dependency.',
                'Regenerate the report for the same selected infrastructure asset and reporting period.',
                'Validate the regenerated artifact before operational use.',
            ),
            'controls': (
                ('Renderer', 'WeasyPrint HTML/PDF'),
                ('Asset Boundary', cluster_scope),
                ('Secondary Scope', namespace_scope),
                ('Reporting Period', period_label),
                ('Data Cut-off', data_cutoff),
                ('Output', 'PDF'),
            ),
        },
    }


def _build_source_metrics(report: Any, payload: Mapping[str, Any]) -> tuple[ReportMetric, ...]:
    metrics = [
        ReportMetric('Template Sections', str(len(report.sections_as_list())), 'Existing template selection', 'info'),
        ReportMetric('Scope', _cluster_scope(report, payload), 'Selected report target', 'info'),
    ]

    for label, key in (
        ('Inventory', 'inventory_status'),
        ('Prometheus', 'prometheus_status'),
        ('Alert Source', 'source_status'),
        ('Integration', 'integration_status'),
    ):
        value = payload.get(key)
        if not isinstance(value, Mapping):
            continue
        status = value.get('label') or value.get('status_label') or value.get('status') or value.get('connected')
        metrics.append(
            ReportMetric(
                label,
                sanitize_text(status, fallback='Unknown'),
                sanitize_text(value.get('description') or value.get('message'), fallback='')[:100],
                tone_from_value(status),
            )
        )
        if len(metrics) >= 4:
            break

    while len(metrics) < 4:
        metrics.append(ReportMetric('Data Source', 'Prepared', 'Renderer input available', 'normal'))
    return tuple(metrics[:4])


def _derive_overall_posture(payload: Mapping[str, Any]) -> tuple[str, str]:
    if payload.get('_error'):
        return 'Limited', 'warning'

    candidates: list[Any] = []

    def collect_status_values(value: Any, *, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(value, Mapping):
            for item_key, item in value.items():
                key_text = str(item_key).lower()
                if any(token in key_text for token in ('status', 'risk', 'severity', 'level')):
                    candidates.append(item)
                if isinstance(item, (Mapping, list, tuple)):
                    collect_status_values(item, depth=depth + 1)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value[:20]:
                collect_status_values(item, depth=depth + 1)

    collect_status_values(payload)
    text = ' '.join(sanitize_text(item, fallback='') for item in candidates).lower()
    if any(token in text for token in ('critical', 'failed', 'unhealthy', 'expired')):
        return 'Critical', 'critical'
    if any(token in text for token in ('warning', 'degraded', 'review', 'stale')):
        return 'Needs Review', 'warning'
    return 'Operational', 'normal'


def _section_status(value: Any) -> tuple[str, str]:
    if isinstance(value, Mapping):
        for key in ('status_label', 'status', 'level', 'risk', 'severity'):
            status = value.get(key)
            if status:
                rendered = sanitize_text(status)
                return rendered, tone_from_value(rendered)
        if value.get('has_data') is False:
            return 'No Data', 'warning'
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return f'{len(value)} Records', 'info'
    return 'Included', 'normal'
