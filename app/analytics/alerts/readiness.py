from __future__ import annotations

from typing import Any

from app.analytics.alerts.contracts import (
    AlertIncidentReadinessCheck,
    AlertIncidentReadinessSummary,
    AlertInhibitionSummary,
    AlertOwnershipSummary,
    AlertRoutingSummary,
    AlertSelectedClusterSignalOverview,
    AlertSilenceSummary,
    AlertSourceHealthSummary,
)


def safe_int(
    value: Any,
    *,
    default: int = 0,
) -> int:
    try:
        return int(
            value or default,
        )
    except (
        TypeError,
        ValueError,
    ):
        return default


def clamp_score(
    value: int,
) -> int:
    return max(
        min(
            value,
            100,
        ),
        0,
    )


def build_incident_readiness(
    *,
    signal_overview: AlertSelectedClusterSignalOverview,
    source_health: AlertSourceHealthSummary,
    routing_summary: AlertRoutingSummary,
    silence_summary: AlertSilenceSummary,
    inhibition_summary: AlertInhibitionSummary,
    ownership_summary: AlertOwnershipSummary,
) -> AlertIncidentReadinessSummary:
    critical_signals = safe_int(
        signal_overview.get(
            'critical_alerts',
            0,
        )
    )
    warning_signals = safe_int(
        signal_overview.get(
            'warning_alerts',
            0,
        )
    )
    anomaly_signals = safe_int(
        signal_overview.get(
            'anomalies',
            0,
        )
    )
    source_score = clamp_score(
        safe_int(
            source_health.get(
                'score',
                0,
            )
        )
    )
    ownership_score = clamp_score(
        safe_int(
            ownership_summary.get(
                'score',
                0,
            )
        )
    )
    matched_silenced_alerts = safe_int(
        silence_summary.get(
            'matched_alerts',
            0,
        )
    )
    inhibited_alerts = safe_int(
        inhibition_summary.get(
            'matched_alerts',
            0,
        )
    )
    routing_ready = bool(
        routing_summary.get(
            'enabled',
            False,
        )
    )

    score = 100

    if critical_signals > 0:
        score -= 25

    if warning_signals > 0:
        score -= 10

    if anomaly_signals > 0:
        score -= 10

    if source_score < 80:
        score -= 15

    if not routing_ready:
        score -= 10

    if ownership_score < 60:
        score -= 15

    if matched_silenced_alerts > 0:
        score -= 10

    if inhibited_alerts > 0:
        score -= 5

    score = clamp_score(
        score,
    )

    if score >= 80:
        level = 'ready'
        label = 'Incident Ready'
        description = (
            'Alert source, routing, ownership, and current signal posture are ready for normal operational monitoring.'
        )
        recommended_action = (
            'Continue monitoring. No immediate incident escalation is required from the current alert posture.'
        )
        icon = 'shield-check'
        class_name = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
    elif score >= 60:
        level = 'watch'
        label = 'Watch Required'
        description = 'Some warning signals or readiness gaps exist. Keep the cluster under closer observation.'
        recommended_action = 'Review warning alerts, confirm ownership metadata, and validate that Alertmanager remains the primary source.'
        icon = 'radar'
        class_name = 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
    elif score >= 40:
        level = 'degraded'
        label = 'Incident Readiness Degraded'
        description = (
            'Alert readiness is degraded because one or more source, routing, metadata, or signal checks are weak.'
        )
        recommended_action = 'Triage active alerts, verify Alertmanager routing, and complete owner/runbook/contact metadata for affected services.'
        icon = 'alert-triangle'
        class_name = 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
    else:
        level = 'incident_risk'
        label = 'Incident Risk'
        description = (
            'Current alert posture has critical signals or significant readiness gaps that may require escalation.'
        )
        recommended_action = 'Escalate critical alerts, assign owner, validate runbook coverage, and inspect muted or inhibited alerts immediately.'
        icon = 'siren'
        class_name = 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-300'

    checks: list[AlertIncidentReadinessCheck] = [
        {
            'label': 'Critical signals',
            'status': 'fail' if critical_signals > 0 else 'pass',
            'description': f'{critical_signals} critical alert signal(s) detected.'
            if critical_signals > 0
            else 'No critical alert signal detected.',
        },
        {
            'label': 'Warning signals',
            'status': 'warning' if warning_signals > 0 else 'pass',
            'description': f'{warning_signals} warning alert signal(s) detected.'
            if warning_signals > 0
            else 'No warning alert signal detected.',
        },
        {
            'label': 'Anomaly signals',
            'status': 'warning' if anomaly_signals > 0 else 'pass',
            'description': f'{anomaly_signals} anomaly candidate(s) detected.'
            if anomaly_signals > 0
            else 'No anomaly candidate detected.',
        },
        {
            'label': 'Alert source health',
            'status': 'pass' if source_score >= 80 else ('warning' if source_score >= 60 else 'fail'),
            'description': f'Source health score is {source_score}/100.',
        },
        {
            'label': 'Routing context',
            'status': 'pass' if routing_ready else 'warning',
            'description': 'Alertmanager routing context is available.'
            if routing_ready
            else 'Routing context is limited or unavailable.',
        },
        {
            'label': 'Ownership readiness',
            'status': 'pass' if ownership_score >= 80 else ('warning' if ownership_score >= 60 else 'fail'),
            'description': f'Ownership and runbook readiness score is {ownership_score}/100.',
        },
        {
            'label': 'Silence impact',
            'status': 'warning' if matched_silenced_alerts > 0 else 'pass',
            'description': f'{matched_silenced_alerts} alert(s) may be affected by active silences.'
            if matched_silenced_alerts > 0
            else 'No active silence currently matches loaded alerts.',
        },
        {
            'label': 'Inhibition impact',
            'status': 'warning' if inhibited_alerts > 0 else 'pass',
            'description': f'{inhibited_alerts} inhibited alert(s) detected.'
            if inhibited_alerts > 0
            else 'No inhibited alert detected from Alertmanager metadata.',
        },
    ]

    return {
        'score': score,
        'level': level,
        'label': label,
        'description': description,
        'class': class_name,
        'icon': icon,
        'critical_signals': critical_signals,
        'warning_signals': warning_signals,
        'anomaly_signals': anomaly_signals,
        'ownership_score': ownership_score,
        'source_score': source_score,
        'silence_risk': matched_silenced_alerts,
        'inhibition_risk': inhibited_alerts,
        'routing_ready': routing_ready,
        'recommended_action': recommended_action,
        'checks': checks,
    }


def build_empty_incident_readiness() -> AlertIncidentReadinessSummary:
    return {
        'score': 0,
        'level': 'incident_risk',
        'label': 'Incident Readiness Unknown',
        'description': 'Incident readiness cannot be evaluated because no alert context is available.',
        'class': 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
        'icon': 'circle-off',
        'critical_signals': 0,
        'warning_signals': 0,
        'anomaly_signals': 0,
        'ownership_score': 0,
        'source_score': 0,
        'silence_risk': 0,
        'inhibition_risk': 0,
        'routing_ready': False,
        'recommended_action': 'Select a cluster and verify alert source configuration before evaluating incident readiness.',
        'checks': [],
    }
