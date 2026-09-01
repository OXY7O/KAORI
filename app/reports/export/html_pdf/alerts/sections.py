from __future__ import annotations

from typing import Any

from .actions import (
    alert_references,
    oldest_label,
    owner_summary,
    ownership_rows,
    recommendation_metrics,
    severity_category_register,
)
from .model import AlertsState, metric, percent, with_ref


def build_cover(state: AlertsState) -> dict[str, str]:
    return {
        'environment': state.environment,
        'purpose': (
            'Support operational review of alert severity, sustained conditions, anomaly evidence, '
            'ownership, and response validation.'
        ),
        'context': (
            'Alert state, anomaly labels, and potential correlations remain separate evidence domains. '
            'Missing anomaly support is not interpreted as no anomaly.'
        ),
    }


def build_executive(state: AlertsState, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'metrics': [
            metric(
                'Critical Alerts',
                str(state.critical_count),
                'Immediate' if state.critical_count else 'Clear',
                'critical' if state.critical_count else 'normal',
            ),
            metric(
                'Warning Alerts',
                str(state.warning_count),
                'Requires Attention' if state.warning_count else 'Clear',
                'warning' if state.warning_count else 'normal',
            ),
            metric('Info Alerts', str(state.info_count), 'Informational', 'info'),
            metric(
                'Anomalies',
                str(state.anomaly_count),
                'Unusual Patterns' if state.anomaly_count else 'None',
                'warning' if state.anomaly_count else 'normal',
            ),
        ],
        'severity_rows': state.severity_rows,
        'category_rows': state.category_rows,
        'interpretation_title': state.executive_title,
        'interpretation_body': state.executive_body,
        'interpretation_note': 'Anomaly evidence and alert category coverage must be validated independently from severity.',
        'tone': state.executive_tone,
        'decisions': recommendations[:4],
    }


def build_severity_category(state: AlertsState) -> dict[str, Any]:
    return {
        'metrics': [
            metric(
                'Active Alerts',
                str(state.active_count),
                'At cut-off',
                'warning' if state.active_count else 'normal',
            ),
            metric('Categorized Alerts', str(state.categorized_count), 'Displayed', 'info'),
            metric(
                'Uncategorized',
                str(state.uncategorized_count),
                'Requires Review' if state.uncategorized_count else 'Clear',
                'warning' if state.uncategorized_count else 'normal',
            ),
            metric(
                'Category Coverage',
                percent(state.category_coverage),
                'Partial' if state.uncategorized_count else 'Complete',
                'warning' if state.uncategorized_count else 'normal',
            ),
        ],
        'severity_rows': state.severity_rows,
        'category_rows': state.category_rows,
        'register': severity_category_register(state),
    }


def build_active_alerts(state: AlertsState) -> dict[str, Any]:
    return {
        'metrics': [
            metric('Displayed Alerts', str(min(len(state.alerts), 8)), 'Top active', 'info'),
            metric(
                'Namespaces',
                str(len({item['namespace'] for item in state.alerts if item['namespace'] != 'Not Available'})),
                'Displayed',
                'normal',
            ),
            metric(
                'Firing State',
                str(sum(1 for item in state.alerts if item['status_key'] == 'firing')),
                'Active',
                'warning',
            ),
            metric(
                'Oldest Since',
                oldest_label(state.alerts),
                'Sustained' if state.alerts else 'Not Available',
                'warning' if state.alerts else 'muted',
            ),
        ],
        'rows': [with_ref(item, f'A{index}') for index, item in enumerate(state.alerts[:8], start=1)],
        'references': alert_references(state.alerts[:5]),
    }


def build_anomalies(state: AlertsState) -> dict[str, Any]:
    evidence_available = sum(1 for item in state.anomalies if item['evidence_available'])
    all_evidenced = bool(state.anomalies) and all(item['evidence_available'] for item in state.anomalies)
    return {
        'metrics': [
            metric(
                'Detected Anomalies',
                str(state.anomaly_count),
                'Committed count',
                'warning' if state.anomaly_count else 'normal',
            ),
            metric('Displayed Records', str(min(len(state.anomalies), 8)), 'Recent', 'info'),
            metric(
                'Evidence Available',
                str(evidence_available),
                'Committed support',
                'normal' if all_evidenced else 'warning',
            ),
            metric(
                'Namespaces',
                str(len({item['namespace'] for item in state.anomalies if item['namespace'] != 'Not Available'})),
                'Displayed',
                'normal',
            ),
        ],
        'rows': [with_ref(item, f'N{index}') for index, item in enumerate(state.anomalies[:8], start=1)],
        'requirements': anomaly_requirements(),
    }


def anomaly_requirements() -> list[dict[str, str]]:
    return [
        {
            'ref': 'E1',
            'evidence': 'Observation Window',
            'definition': 'Start, end, and comparison baseline',
            'status': 'Missing',
            'action': 'Required',
        },
        {
            'ref': 'E2',
            'evidence': 'Signal Evidence',
            'definition': 'Metric, expected band, and deviation',
            'status': 'Missing',
            'action': 'Required',
        },
        {
            'ref': 'E3',
            'evidence': 'Entity Identity',
            'definition': 'Pod, workload, namespace, and owner',
            'status': 'Partial',
            'action': 'Required',
        },
        {
            'ref': 'E4',
            'evidence': 'Correlation Evidence',
            'definition': 'Related alerts, events, and changes',
            'status': 'Missing',
            'action': 'Required',
        },
    ]


def build_ownership(state: AlertsState) -> dict[str, Any]:
    return {
        'metrics': [
            metric(
                'Sustained Alerts',
                str(sum(1 for item in state.alerts if item['starts_at_display'] != 'Not Available')),
                'Displayed',
                'warning',
            ),
            metric(
                'Owner Coverage',
                str(sum(1 for item in state.alerts if item['owner'] != 'Not Available')),
                'Committed',
                'normal'
                if state.alerts and all(item['owner'] != 'Not Available' for item in state.alerts)
                else 'warning',
            ),
            metric(
                'Runbook Coverage',
                str(sum(1 for item in state.alerts if item['runbook'] != 'Not Available')),
                'Committed',
                'normal'
                if state.alerts and all(item['runbook'] != 'Not Available' for item in state.alerts)
                else 'warning',
            ),
            metric('Response Validation', 'Required', 'All displayed', 'info'),
        ],
        'rows': ownership_rows(state),
    }


def build_correlation(state: AlertsState, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'metrics': [
            metric(
                'Alert Records',
                str(state.active_count),
                'Active count',
                'warning' if state.active_count else 'normal',
            ),
            metric(
                'Anomaly Records',
                str(state.anomaly_count),
                'Detected count',
                'warning' if state.anomaly_count else 'normal',
            ),
            metric('Direct Correlations', '0', 'Not committed', 'warning'),
            metric('Evidence Quality', 'Partial', 'Review', 'warning'),
        ],
        'rows': rows,
    }


def build_recommendations_section(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'metrics': recommendation_metrics(recommendations),
        'rows': recommendations,
        'governance': [
            {
                'field': 'Primary Action',
                'requirement': (
                    recommendations[0]['title'] if recommendations else 'Continue alert and anomaly monitoring.'
                ),
            },
            {
                'field': 'Validation Criteria',
                'requirement': (
                    'Confirm live alert state, expected workload behavior, events, metrics, accountable owner, '
                    'and approved response before closure.'
                ),
            },
            {'field': 'Assigned Owners', 'requirement': owner_summary(recommendations)},
            {
                'field': 'Change Control',
                'requirement': 'No workload or infrastructure change is authorized by this report alone.',
            },
        ],
    }


def build_methodology(
    state: AlertsState,
    *,
    source_rows: list[dict[str, str]],
    period_label: str,
    data_cutoff: str,
) -> dict[str, Any]:
    return {
        'metrics': [
            metric('Data Sources', str(len(source_rows)), 'Committed', 'normal'),
            metric(
                'Active Alerts',
                str(state.active_count),
                'At cut-off',
                'warning' if state.active_count else 'normal',
            ),
            metric(
                'Anomalies',
                str(state.anomaly_count),
                'Committed count',
                'warning' if state.anomaly_count else 'normal',
            ),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ],
        'sources': source_rows,
        'rules': [
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
            {'ref': 'M3', 'rule': 'Severity', 'setting': 'Committed labels'},
            {'ref': 'M4', 'rule': 'Category Coverage', 'setting': 'Displayed categories'},
            {'ref': 'M5', 'rule': 'Anomaly Evidence', 'setting': 'Explicit Not Available'},
        ],
        'included': [
            'Committed alert severity, namespace, start time, ownership metadata, and firing state.',
            'Displayed alert-category counts and committed source health when available.',
            'Committed anomaly count and recent anomaly labels.',
        ],
        'excluded': [
            'Live alert state after the report cut-off.',
            'Uncommitted root cause, causal correlation, and business impact.',
            'Missing anomaly metric, event, and comparison evidence.',
        ],
        'limitations': [
            'Alert severity does not establish business impact.',
            'Category coverage and anomaly support may be partial.',
            'Validate all actions against live state before remediation.',
        ],
        'status_language': [
            {'ref': 'S1', 'title': 'Not Available', 'description': 'No supporting evidence exists.'},
            {
                'ref': 'S2',
                'title': 'Partial Coverage',
                'description': 'Only part of the active set is categorized or evidenced.',
            },
            {'ref': 'S3', 'title': 'Firing', 'description': 'The alert was active at the committed cut-off.'},
            {'ref': 'S4', 'title': 'Unconfirmed', 'description': 'A relationship is a review lead, not causality.'},
        ],
    }
