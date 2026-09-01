from __future__ import annotations

from typing import Any

from .actions import (
    build_recommendations,
    build_risk_rows,
    build_source_evidence,
    owner_summary,
    primary_interpretation,
    recommendation_metrics,
)
from .context import TopConsumersContext
from .model import (
    PAGE_COUNT,
    TopConsumersState,
    build_top_consumers_state,
    display_total,
    metric,
    resource_page,
    risk_count,
    unit,
)


def build_top_consumers_presentation(context: TopConsumersContext) -> dict[str, Any]:
    state = build_top_consumers_state(context.payload)
    recommendations = build_recommendations(
        state.consumer_payload,
        state.cpu_rows,
        state.memory_rows,
    )
    interpretation = primary_interpretation(state.cpu_rows, state.memory_rows)
    source_evidence = build_source_evidence(context.payload, state.metrics_source)

    return {
        'presentation_version': 'v3.0-top-consumers-publication',
        'page_count': PAGE_COUNT,
        'report_id': context.report_id,
        'report_name': context.report_name,
        'report_title': 'Top Consumers',
        'cluster_scope': context.cluster_scope,
        'namespace_scope': context.namespace_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at,
        'generated_by': context.generated_by,
        'classification': context.classification,
        'cover': build_cover(state),
        'executive': build_executive(state, recommendations, interpretation),
        'cpu': resource_page('CPU', state.cpu_rows, state.top_cpu, '#2563EB'),
        'memory': resource_page('Memory', state.memory_rows, state.top_memory, '#7C3AED'),
        'namespace': build_namespace(state),
        'comparison': build_comparison(state),
        'risk': build_risk(state, recommendations),
        'recommendations': build_recommendation_section(recommendations),
        'methodology': build_methodology(context, state, source_evidence),
    }


def build_cover(state: TopConsumersState) -> dict[str, str]:
    return {
        'environment': state.environment,
        'purpose': (
            'Support operational review of leading resource contributors, displayed concentration, '
            'ownership, and validation actions.'
        ),
        'context': (
            'Rankings describe the committed displayed consumer set. They do not establish complete '
            'namespace allocation or aggregate capacity pressure.'
        ),
    }


def build_executive(
    state: TopConsumersState,
    recommendations: list[dict[str, Any]],
    interpretation: dict[str, str],
) -> dict[str, Any]:
    return {
        'metrics': [
            metric('Displayed CPU', display_total(state.cpu_rows, state.cpu_total), 'Top 3 total', 'info'),
            metric(
                'Displayed Memory',
                display_total(state.memory_rows, state.memory_total),
                'Top 3 total',
                'warning',
            ),
            metric(
                'CPU Namespaces',
                str(len({row['namespace'] for row in state.cpu_rows})),
                'Displayed set',
                'normal',
            ),
            metric(
                'Memory Namespace',
                state.memory_namespace_label,
                'Concentration',
                'warning' if len(state.memory_namespaces) == 1 else 'muted',
            ),
        ],
        'cpu_rows': state.cpu_rows,
        'memory_rows': state.memory_rows,
        'interpretation_title': interpretation['title'],
        'interpretation_body': interpretation['body'],
        'interpretation_note': interpretation['note'],
        'tone': interpretation['tone'],
        'decisions': recommendations[:4],
    }


def build_namespace(state: TopConsumersState) -> dict[str, Any]:
    return {
        'metrics': [
            metric(
                'CPU Namespaces',
                str(len({row['namespace'] for row in state.cpu_rows})),
                'Displayed',
                'normal',
            ),
            metric(
                'Memory Namespaces',
                str(len(state.memory_namespaces)),
                'Displayed',
                'warning' if len(state.memory_namespaces) == 1 else 'normal',
            ),
            metric(
                'Displayed Records',
                str(len(state.cpu_rows) + len(state.memory_rows)),
                'CPU + Memory',
                'info',
            ),
            metric('Denominator', 'Partial', 'Displayed set only', 'warning'),
        ],
        'cpu_rows': state.cpu_namespace_rows,
        'memory_rows': state.memory_namespace_rows,
        'register': state.namespace_rows,
    }


def build_comparison(state: TopConsumersState) -> dict[str, Any]:
    return {
        'metrics': [
            metric('CPU Unit', unit(state.cpu_rows, fallback='cores'), 'Normalized', 'info'),
            metric('Memory Unit', unit(state.memory_rows, fallback='GiB'), 'Normalized', 'warning'),
            metric('Ranking Scope', 'Top 3', 'Per signal', 'normal'),
            metric('Trend Evidence', 'N/A', 'Not Available', 'warning'),
        ],
        'rows': state.comparison_rows,
    }


def build_risk(
    state: TopConsumersState,
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    critical_count = risk_count(state.normalized_rows, 'critical')
    return {
        'metrics': [
            metric(
                'Critical Risks',
                str(critical_count),
                'Consumer pressure',
                'critical' if critical_count else 'normal',
            ),
            metric(
                'Review Risks',
                str(risk_count(state.normalized_rows, 'warning')),
                'Open',
                'warning',
            ),
            metric(
                'Evidence Gaps',
                str(state.partial_count + state.unavailable_count),
                'Coverage',
                'warning' if state.partial_count + state.unavailable_count else 'normal',
            ),
            metric('Validation Gates', str(len(recommendations)), 'Required', 'info'),
        ],
        'rows': build_risk_rows(state.normalized_rows, recommendations),
    }


def build_recommendation_section(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'metrics': recommendation_metrics(recommendations),
        'rows': recommendations,
        'governance': [
            {
                'field': 'Primary Action',
                'requirement': (
                    recommendations[0]['title'] if recommendations else 'Continue consumer evidence monitoring.'
                ),
            },
            {
                'field': 'Validation Criteria',
                'requirement': (
                    'Confirm expected workload behavior, accountable owner, ranking denominator, '
                    'live metric, and approved response before closure.'
                ),
            },
            {'field': 'Assigned Owners', 'requirement': owner_summary(recommendations)},
            {
                'field': 'Change Control',
                'requirement': 'No infrastructure or workload change is authorized by this report alone.',
            },
        ],
    }


def build_methodology(
    context: TopConsumersContext,
    state: TopConsumersState,
    source_evidence: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        'metrics': [
            metric('Data Sources', str(len(source_evidence)), 'Committed', 'normal'),
            metric('Coverage', state.coverage_label, 'Resource evidence', state.coverage_tone),
            metric('Ranking Scope', 'Top 3', 'Per resource', 'info'),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ],
        'sources': source_evidence,
        'rules': [
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': context.period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': context.data_cutoff},
            {'ref': 'M3', 'rule': 'Memory Unit', 'setting': 'Source display / GiB normalization'},
            {'ref': 'M4', 'rule': 'Contribution Share', 'setting': 'Displayed top-set total'},
            {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
        ],
        'included': [
            'Committed displayed top-consumer records and normalized resource values.',
            'Displayed-set contribution shares calculated independently per resource.',
            'Namespace, pressure, request, limit, and recommendation evidence when committed.',
        ],
        'excluded': [
            'Complete namespace or cluster allocation denominator unless explicitly committed.',
            'Consumer-level historical direction and service objectives when unavailable.',
            'Live state after the data cut-off and uncommitted application ownership.',
        ],
        'limitations': [
            'Top-consumer ranking describes displayed records only.',
            'Different resource units are not combined into a single score.',
            'Validate all recommendations against live state before remediation.',
        ],
        'status_language': [
            {'ref': 'S1', 'title': 'Not Available', 'description': 'No committed evidence exists.'},
            {
                'ref': 'S2',
                'title': 'Partial Coverage',
                'description': 'Only part of the requested scope is represented.',
            },
            {
                'ref': 'S3',
                'title': 'Current Only',
                'description': 'A cut-off value exists without historical direction.',
            },
            {
                'ref': 'S4',
                'title': 'Source Unavailable',
                'description': 'The source was unreachable at the cut-off.',
            },
        ],
    }
