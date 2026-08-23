from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.constants import ANALYTICS_REPORT_RECOMMENDATIONS
from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)
from app.reports.export.html_pdf.builder_context import ReportDocumentContext
from app.reports.export.html_pdf.normalization import sanitize_text

_OBJECT_STORAGE_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'Capacity & Governance',
    'Request & Reliability',
    'Forecast Outlook',
    'Consumer Concentration',
    'Risk & Recommendations',
    'Methodology & Evidence Boundary',
)

_TONE_MAP = {
    'normal': 'normal',
    'healthy': 'normal',
    'ready': 'normal',
    'current': 'normal',
    'baseline': 'normal',
    'warning': 'warning',
    'warn': 'warning',
    'attention': 'warning',
    'review': 'warning',
    'critical': 'critical',
    'error': 'critical',
    'failed': 'critical',
    'info': 'info',
    'blue': 'info',
    'unknown': 'muted',
    'partial': 'muted',
    'neutral': 'muted',
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any, fallback: str = 'Not Available') -> str:
    return sanitize_text(value, fallback=fallback)


def _tone(value: Any, fallback: str = 'muted') -> str:
    raw = _text(value, fallback).lower()
    return _TONE_MAP.get(raw, fallback)


def _metric(label: str, value: Any, status: str, tone: str = 'muted') -> dict[str, str]:
    return {
        'label': label,
        'value': _text(value),
        'status': status,
        'tone': tone,
    }


def _risk_item(raw: Mapping[str, Any], index: int) -> dict[str, str]:
    severity = _text(raw.get('severity') or raw.get('tone') or raw.get('status'), 'unknown').lower()
    tone = _tone(severity)
    title = _text(
        raw.get('title') or raw.get('alertname') or raw.get('name') or raw.get('summary'),
        f'Operational finding {index}',
    )
    detail = _text(
        raw.get('detail') or raw.get('description') or raw.get('summary') or raw.get('message'),
        'Review committed evidence and confirm current operational state.',
    )
    return {
        'ref': f'R{index}',
        'severity': severity.title() if severity != 'unknown' else 'Review',
        'tone': tone,
        'title': title,
        'detail': detail,
    }


def _risk_counts(rows: list[dict[str, str]]) -> tuple[int, int, int]:
    critical = sum(item['tone'] == 'critical' for item in rows)
    warning = sum(item['tone'] == 'warning' for item in rows)
    review = sum(item['tone'] not in {'critical', 'warning', 'normal'} for item in rows)
    return critical, warning, review


def _consumer_rows(bucket_rows: Sequence[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, raw in enumerate(bucket_rows[:5], start=1):
        item = _mapping(raw)
        rows.append(
            {
                'ref': f'B{index}',
                'name': _text(item.get('name'), f'Bucket {index}'),
                'usage': _text(item.get('usage_display')),
                'share': _text(item.get('usage_share_display')),
                'objects': _text(item.get('objects_display')),
                'quota': _text(item.get('quota_display')),
            }
        )
    return rows


def _management_summary(
    capacity: Mapping[str, Any],
    bucket_analysis: Mapping[str, Any],
    performance: Mapping[str, Any],
    forecast: Mapping[str, Any],
) -> str:
    return (
        f'Current utilization is {_text(capacity.get("utilization"))} with '
        f'{_text(capacity.get("headroom"))} remaining headroom. '
        f'The largest bucket represents {_text(bucket_analysis.get("top_usage_share_display"))} of known usage. '
        f'Request error ratio is {_text(performance.get("error_ratio_display") or performance.get("error_ratio"), "N/A")}. '
        f'The 30-day storage projection is {_text(forecast.get("projected_30d"))}.'
    )


def build_object_storage_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    """Build the management-first Object Storage Analytics Overview contract.

    The analytical PDF intentionally avoids reproducing Object Storage inventory rows.
    Long bucket identities are represented through stable references and a compact
    top-consumer register. Detailed bucket evidence remains in Object Storage Inventory.
    """

    system = _mapping(payload.get('system') or payload.get('selected_system'))
    summary = _mapping(payload.get('summary'))
    capacity = _mapping(payload.get('capacity_usage'))
    bucket_analysis = _mapping(payload.get('bucket_analysis'))
    performance = _mapping(payload.get('performance'))
    forecast = _mapping(payload.get('forecast_display'))
    forecast_materialization = _mapping(payload.get('forecast_materialization'))
    metrics_source = _mapping(payload.get('metrics_source'))
    metrics_readiness = _mapping(payload.get('metrics_readiness'))
    evidence_boundary = _mapping(payload.get('evidence_boundary'))
    signal_posture = _mapping(payload.get('signal_posture'))

    consumers = _consumer_rows(_sequence(payload.get('top_consumers') or payload.get('bucket_rows')))
    risk_rows = [
        _risk_item(_mapping(item), index)
        for index, item in enumerate(_sequence(payload.get('risk_findings'))[:4], start=1)
        if isinstance(item, Mapping)
    ]
    critical_count, warning_count, review_count = _risk_counts(risk_rows)

    bucket_count = _text(bucket_analysis.get('bucket_count') or summary.get('buckets'), '0')
    quota_coverage = _text(bucket_analysis.get('quota_evidence_coverage_display'))
    top_share = _text(bucket_analysis.get('top_usage_share_display'))
    concentration = _text(bucket_analysis.get('concentration_label'), 'Unknown')
    concentration_tone = _tone(bucket_analysis.get('concentration_tone'))
    request_rate = _text(performance.get('request_rate_display') or performance.get('request_rate'), 'N/A')
    error_ratio = _text(performance.get('error_ratio_display') or performance.get('error_ratio'), 'N/A')
    success_ratio = _text(performance.get('success_ratio_display') or performance.get('success_ratio'), 'N/A')
    offline_nodes = _text(performance.get('offline_nodes_display') or performance.get('offline_nodes'), 'N/A')

    recommendations = tuple(
        {
            'ref': f'A{index}',
            'priority': 'P2' if index < 3 else 'P3',
            'title': _text(item),
            'owner': 'Platform Operations',
            'status': 'Open' if risk_rows else 'Monitor',
            'tone': 'warning' if risk_rows else 'normal',
        }
        for index, item in enumerate(ANALYTICS_REPORT_RECOMMENDATIONS.get('object_storage_analysis', ()), start=1)
    )

    metrics_contract = _text(
        metrics_readiness.get('label') or metrics_readiness.get('status'),
        'Evidence Boundary Recorded',
    )
    source_label = _text(
        metrics_source.get('provider_label') or metrics_source.get('label'),
        'Object Storage Evidence',
    )
    forecast_state = _text(
        forecast_materialization.get('label') or forecast_materialization.get('status'),
        'Not Available',
    )

    common = {
        'presentation_version': 'v3.0-object-storage-overview-standard',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': analytics_layout_contract(
            page_count=len(_OBJECT_STORAGE_PAGE_TITLES),
            table_policy='concise-register-plus-reference',
            dynamic_section_policy='management-overview-pages',
            identity_policy='reference-register',
            inventory_detail_policy='excluded-from-analytics-pdf',
        ),
        'report_id': context.report_id,
        'report_name': context.report_name,
        'report_title': 'Object Storage Analytics Overview',
        'report_subtitle': 'Object Storage Operational Intelligence Report',
        'report_purpose': (
            'A management-first view of Object Storage capacity, governance, reliability, forecast, '
            'consumer concentration, and operational risk.'
        ),
        'classification': classification,
        'page_count': len(_OBJECT_STORAGE_PAGE_TITLES),
        'page_titles': _OBJECT_STORAGE_PAGE_TITLES,
        'scope_value': context.cluster_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at_label,
        'generated_by': context.generated_by_label,
        'source_label': source_label,
        'metrics_contract': metrics_contract,
        'environment': _text(system.get('environment'), 'Not Available'),
    }

    executive = {
        'metrics': (
            _metric('Capacity', capacity.get('capacity_total') or summary.get('capacity'), 'Committed', 'normal'),
            _metric('Usage', capacity.get('usage_total') or summary.get('usage'), 'Observed', 'normal'),
            _metric('Headroom', capacity.get('headroom'), 'Remaining', _tone(capacity.get('capacity_posture'))),
            _metric('Buckets', bucket_count, 'Committed Scope', 'normal'),
        ),
        'headline': _text(
            signal_posture.get('detail'),
            'Current Object Storage evidence is available for management review.',
        ),
        'summary': _management_summary(capacity, bucket_analysis, performance, forecast),
        'posture_rows': (
            {'ref': 'E1', 'dimension': 'Capacity', 'value': _text(capacity.get('utilization')), 'state': 'Utilization'},
            {'ref': 'E2', 'dimension': 'Quota Coverage', 'value': quota_coverage, 'state': 'Governance'},
            {'ref': 'E3', 'dimension': 'Request Reliability', 'value': error_ratio, 'state': 'Error Ratio'},
            {'ref': 'E4', 'dimension': 'Consumer Concentration', 'value': top_share, 'state': concentration},
        ),
    }

    capacity_page = {
        'metrics': (
            _metric('Capacity Total', capacity.get('capacity_total') or summary.get('capacity'), 'Committed', 'normal'),
            _metric('Usage Total', capacity.get('usage_total') or summary.get('usage'), 'Observed', 'normal'),
            _metric('Headroom', capacity.get('headroom'), 'Remaining', 'normal'),
            _metric('Quota Coverage', quota_coverage, 'Observed Buckets', _tone(bucket_analysis.get('quota_tone'))),
        ),
        'rows': (
            {
                'ref': 'C1',
                'dimension': 'Utilization',
                'value': _text(capacity.get('utilization')),
                'status': 'Current',
                'tone': 'normal',
            },
            {
                'ref': 'C2',
                'dimension': 'Buckets in Scope',
                'value': bucket_count,
                'status': 'Committed',
                'tone': 'normal',
            },
            {
                'ref': 'C3',
                'dimension': 'Quota Configured',
                'value': _text(bucket_analysis.get('quota_configured_count'), '0'),
                'status': 'Observed',
                'tone': 'normal',
            },
            {
                'ref': 'C4',
                'dimension': 'Quota Pressure',
                'value': _text(bucket_analysis.get('quota_pressure_count'), '0'),
                'status': 'Review' if _text(bucket_analysis.get('quota_pressure_count'), '0') != '0' else 'Clear',
                'tone': 'warning' if _text(bucket_analysis.get('quota_pressure_count'), '0') != '0' else 'normal',
            },
        ),
        'interpretation': (
            f'Quota evidence covers {quota_coverage} of committed bucket scope. '
            f'Consumer concentration is {concentration.lower()}, with the largest bucket representing {top_share} of known usage.'
        ),
        'concentration': concentration,
        'concentration_tone': concentration_tone,
    }

    reliability_page = {
        'metrics': (
            _metric('Request Rate', request_rate, 'Current Demand', 'info'),
            _metric('Error Ratio', error_ratio, 'Reliability', _tone(performance.get('reliability_tone'))),
            _metric('Success Ratio', success_ratio, 'Successful Requests', 'normal'),
            _metric('Offline Nodes', offline_nodes, 'Node Availability', _tone(performance.get('node_tone'))),
        ),
        'rows': (
            {
                'ref': 'P1',
                'signal': 'Request Demand',
                'value': request_rate,
                'assessment': _text(performance.get('request_trend_status'), 'Current'),
            },
            {
                'ref': 'P2',
                'signal': 'Error Ratio',
                'value': error_ratio,
                'assessment': _text(performance.get('reliability_status'), 'Review'),
            },
            {
                'ref': 'P3',
                'signal': 'Queue',
                'value': _text(performance.get('waiting_display') or performance.get('waiting'), 'N/A'),
                'assessment': _text(performance.get('queue_status'), 'Review'),
            },
            {
                'ref': 'P4',
                'signal': 'Traffic',
                'value': _text(performance.get('total_traffic_display') or performance.get('traffic'), 'N/A'),
                'assessment': 'Observed',
            },
        ),
        'interpretation': (
            f'Current request demand is {request_rate} with an observed error ratio of {error_ratio}. '
            f'Offline-node evidence is {offline_nodes}; queue and node state must remain separate from capacity posture.'
        ),
    }

    forecast_page = {
        'metrics': (
            _metric('Growth / Day', forecast.get('growth_per_day'), forecast_state, 'info'),
            _metric('Projected 7d', forecast.get('projected_7d'), 'Planning', 'info'),
            _metric('Projected 30d', forecast.get('projected_30d'), 'Planning', 'info'),
            _metric(
                'Capacity ETA',
                forecast.get('days_to_capacity'),
                'Planning Horizon',
                'warning' if 'N/A' not in _text(forecast.get('days_to_capacity')) else 'muted',
            ),
        ),
        'rows': (
            {
                'ref': 'F1',
                'dimension': 'Current Usage',
                'value': _text(capacity.get('usage_total') or summary.get('usage')),
                'assessment': 'Committed',
            },
            {
                'ref': 'F2',
                'dimension': '7-day Projection',
                'value': _text(forecast.get('projected_7d')),
                'assessment': 'Planning',
            },
            {
                'ref': 'F3',
                'dimension': '30-day Projection',
                'value': _text(forecast.get('projected_30d')),
                'assessment': 'Planning',
            },
            {
                'ref': 'F4',
                'dimension': 'Capacity ETA',
                'value': _text(forecast.get('days_to_capacity')),
                'assessment': forecast_state,
            },
        ),
        'interpretation': (
            'Forecast values are planning evidence only. Validate current demand, approved growth, and live capacity '
            'before changing Object Storage topology or capacity.'
        ),
    }

    consumer_page = {
        'metrics': (
            _metric('Buckets', bucket_count, 'Committed Scope', 'normal'),
            _metric('Largest Share', top_share, concentration, concentration_tone),
            _metric('Top Consumer', consumers[0]['usage'] if consumers else 'Not Available', 'Displayed Usage', 'info'),
            _metric('Displayed Set', str(len(consumers)), 'Top Consumers', 'normal' if consumers else 'muted'),
        ),
        'rows': consumers,
        'interpretation': (
            f'The largest bucket represents {top_share} of known usage. The analytical PDF shows only the top '
            'consumer set; complete bucket inventory remains in Object Storage Inventory.'
        ),
    }

    risk_page = {
        'metrics': (
            _metric(
                'Critical Findings', str(critical_count), 'Operational Risk', 'critical' if critical_count else 'normal'
            ),
            _metric(
                'Warning Findings', str(warning_count), 'Requires Review', 'warning' if warning_count else 'normal'
            ),
            _metric('Other Review', str(review_count), 'Evidence Review', 'warning' if review_count else 'normal'),
            _metric('Actions', str(len(recommendations)), 'Management Follow-up', 'info'),
        ),
        'rows': tuple(risk_rows),
        'recommendations': recommendations,
        'interpretation': (
            'Assign ownership to actionable findings, validate live state, and preserve evidence boundaries before remediation. '
            'Normal aggregate posture does not clear localized or governance risk.'
        ),
    }

    methodology_page = {
        'metrics': (
            _metric('Inventory Source', evidence_boundary.get('inventory_source'), 'Committed', 'normal'),
            _metric('Metrics Source', source_label, metrics_contract, 'info'),
            _metric('Forecast State', forecast_state, 'Materialized Evidence', 'info'),
            _metric('Alert Source', evidence_boundary.get('alert_source'), 'Provider Context', 'info'),
        ),
        'sources': (
            {
                'source': _text(evidence_boundary.get('inventory_source')),
                'freshness': 'Snapshot',
                'last_collected': _text(evidence_boundary.get('inventory_cutoff'), context.data_cutoff),
            },
            {'source': source_label, 'freshness': context.period_label, 'last_collected': context.data_cutoff},
            {'source': 'Object Storage Forecast', 'freshness': forecast_state, 'last_collected': context.data_cutoff},
        ),
        'rules': (
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': context.period_label},
            {'ref': 'M2', 'rule': 'Data Cut-off', 'setting': context.data_cutoff},
            {'ref': 'M3', 'rule': 'Analytics Detail', 'setting': 'Management summary; top consumers only'},
            {'ref': 'M4', 'rule': 'Inventory Detail', 'setting': 'Object Storage Inventory workbook'},
        ),
        'included': (
            'Committed system capacity, usage, quota governance, request reliability, and forecast evidence.',
            'Top-consumer concentration represented through stable references and concise comparison fields.',
            'Metric-derived and provider-owned operational risk available at the report cut-off.',
        ),
        'excluded': (
            'Full bucket/container inventory and every technical metadata field.',
            'Live state after the report cut-off and uncommitted provider observations.',
            'Autonomous remediation or change authorization.',
        ),
    }

    return {
        **common,
        'executive': executive,
        'capacity': capacity_page,
        'reliability': reliability_page,
        'forecast': forecast_page,
        'consumers': consumer_page,
        'risk': risk_page,
        'methodology': methodology_page,
    }
