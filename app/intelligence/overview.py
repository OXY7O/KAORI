from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func

from app.common.automation_execution import execution_enabled
from app.extensions.db import db
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.rule_presentation import normalize_rule
from app.intelligence.service import get_active_recommendation_findings
from app.models.alert_ops import AlertCase, AlertSilence
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceDecision, IntelligenceDecisionCandidate, IntelligenceExecutionJournal
from app.models.knowledge import KnowledgeRunbookRevision
from app.models.notification_channel import NotificationDelivery
from app.models.object_storage import ObjectStorageSystem


def get_intelligence_overview_payload() -> dict[str, Any]:
    findings = get_active_recommendation_findings()
    catalog = [normalize_rule(dict(rule)) for rule in INTELLIGENCE_CATALOG]

    critical = sum(1 for item in findings if item.get('severity') == 'critical')
    warning = sum(1 for item in findings if item.get('severity') == 'warning')
    active_domains = {str(item.get('domain') or '') for item in findings if item.get('domain')}

    clusters = Cluster.query.count()
    storage_systems = ObjectStorageSystem.query.count()
    registered_assets = clusters + storage_systems
    available_domains = int(clusters > 0) + int(storage_systems > 0)

    available_rules = sum(1 for rule in catalog if rule.get('status') == 'available')
    reserved_rules = sum(1 for rule in catalog if rule.get('status') == 'reserved')
    imported_rules = sum(1 for rule in catalog if rule.get('status') == 'imported_signal')

    automation = _automation_summary()
    alerts = _alert_operations_summary()
    assets = {
        'kubernetes': clusters,
        'object_storage': storage_systems,
    }
    summary = {
        'findings': len(findings),
        'critical': critical,
        'warning': warning,
        'active_domains': len(active_domains),
        'registered_assets': registered_assets,
        'available_domains': available_domains,
        'catalog_rules': len(catalog),
        'available_rules': available_rules,
        'reserved_rules': reserved_rules,
        'imported_rules': imported_rules,
        'pending_automation': automation['pending_governance'],
    }

    posture = _overview_posture(
        registered_assets=registered_assets,
        critical_findings=critical,
        warning_findings=warning,
        findings=len(findings),
        critical_alerts=alerts['critical'],
        active_alerts=alerts['active'],
        verification_pending=alerts['verification_pending'],
        delivery_failures=alerts['delivery_failures'],
        automation_failures=automation['failures'],
        pending_automation=automation['pending_governance'],
    )

    return {
        'posture': posture,
        'summary': summary,
        'assets': assets,
        'alerts': alerts,
        'automation': automation,
        'attention_metrics': _attention_metrics(summary=summary, alerts=alerts, automation=automation),
        'coverage_metrics': _coverage_metrics(summary=summary, assets=assets, alerts=alerts, automation=automation),
        'workspaces': _workspace_rows(summary=summary, alerts=alerts, automation=automation),
    }


def _automation_summary() -> dict[str, Any]:
    pending_candidates = IntelligenceDecisionCandidate.query.filter_by(review_status='pending').count()
    awaiting_approval = IntelligenceDecision.query.filter_by(workflow_status='pending_approval').count()
    failures = IntelligenceExecutionJournal.query.filter(
        db.or_(
            IntelligenceExecutionJournal.orchestration_status == 'dead_letter',
            IntelligenceExecutionJournal.status == 'failed',
        )
    ).count()
    published_runbooks = KnowledgeRunbookRevision.query.filter_by(publication_status='published').count()
    enabled = execution_enabled()
    pending_governance = pending_candidates + awaiting_approval

    if failures:
        posture = {'label': 'Control Attention', 'tone': 'warning'}
    elif pending_governance:
        posture = {'label': 'Review Required', 'tone': 'warning'}
    elif enabled:
        posture = {'label': 'Controlled Execution', 'tone': 'normal'}
    else:
        posture = {'label': 'Governance Only', 'tone': 'info'}

    return {
        'pending_candidates': pending_candidates,
        'awaiting_approval': awaiting_approval,
        'pending_governance': pending_governance,
        'failures': failures,
        'published_runbooks': published_runbooks,
        'execution_enabled': enabled,
        'execution_label': 'Enabled' if enabled else 'Execution Disabled',
        'posture': posture,
    }


def _alert_operations_summary() -> dict[str, int]:
    now = datetime.now(UTC)
    alert_counts = db.session.query(
        func.sum(case((AlertCase.workflow_state != 'closed', 1), else_=0)),
        func.sum(
            case(
                (
                    and_(AlertCase.workflow_state != 'closed', AlertCase.severity == 'critical'),
                    1,
                ),
                else_=0,
            )
        ),
        func.sum(case((AlertCase.workflow_state == 'acknowledged', 1), else_=0)),
        func.sum(case((AlertCase.workflow_state == 'verification_pending', 1), else_=0)),
        func.sum(
            case(
                (
                    and_(
                        AlertCase.workflow_state == 'closed',
                        AlertCase.closed_at.is_not(None),
                        AlertCase.closed_at >= now - timedelta(days=1),
                    ),
                    1,
                ),
                else_=0,
            )
        ),
        func.sum(case((AlertCase.postmortem_status.in_(('required', 'draft')), 1), else_=0)),
    ).one()
    active_silences = AlertSilence.query.filter(
        AlertSilence.starts_at <= now,
        AlertSilence.ends_at > now,
        AlertSilence.revoked_at.is_(None),
    ).count()
    delivery_failures = NotificationDelivery.query.filter(
        NotificationDelivery.event_type.in_(('alert_ops.firing', 'alert_ops.resolved')),
        NotificationDelivery.status == 'failed',
    ).count()

    active, critical, acknowledged, verification_pending, closed_24h, postmortem_required = (
        int(value or 0) for value in alert_counts
    )
    return {
        'active': active,
        'critical': critical,
        'acknowledged': acknowledged,
        'verification_pending': verification_pending,
        'silenced': int(active_silences),
        'resolved_24h': closed_24h,
        'delivery_failures': int(delivery_failures),
        'postmortem_required': postmortem_required,
    }


def _overview_posture(
    *,
    registered_assets: int,
    critical_findings: int,
    warning_findings: int,
    findings: int,
    critical_alerts: int,
    active_alerts: int,
    verification_pending: int,
    delivery_failures: int,
    automation_failures: int,
    pending_automation: int,
) -> dict[str, str]:
    critical_total = critical_findings + critical_alerts
    if critical_total:
        return {
            'label': 'Critical Review',
            'tone': 'critical',
            'helper': (
                f'{critical_total} critical intelligence signal(s) require immediate operator review '
                'across Recommendations and Alert Operations.'
            ),
        }
    if delivery_failures or automation_failures:
        return {
            'label': 'Control Attention',
            'tone': 'warning',
            'helper': (
                f'{delivery_failures + automation_failures} delivery or automation control failure(s) '
                'require operational review.'
            ),
        }
    if warning_findings or verification_pending or pending_automation:
        return {
            'label': 'Review Required',
            'tone': 'warning',
            'helper': (
                'Warnings, verification-pending alert cases, or governed automation decisions '
                'currently require operator attention.'
            ),
        }
    if findings or active_alerts:
        return {
            'label': 'Active Intelligence',
            'tone': 'info',
            'helper': (
                f'{findings} recommendation finding(s) and {active_alerts} active alert case(s) '
                'are available for operational review.'
            ),
        }
    if registered_assets == 0:
        return {
            'label': 'No Managed Assets',
            'tone': 'unknown',
            'helper': (
                'Rule, alert-lifecycle, and automation governance remain visible, '
                'but no managed infrastructure asset is registered yet.'
            ),
        }
    return {
        'label': 'Operationally Clear',
        'tone': 'normal',
        'helper': 'No current Intelligence signal requires immediate operator action.',
    }


def _attention_metrics(
    *,
    summary: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            'label': 'Critical Recommendations',
            'value': summary['critical'],
            'supporting': f'{summary["warning"]} warning findings',
            'icon': 'sparkles',
            'tone': 'critical' if summary['critical'] else ('warning' if summary['warning'] else 'normal'),
            'status': 'Critical' if summary['critical'] else ('Review' if summary['warning'] else 'Clear'),
        },
        {
            'label': 'Active Alert Cases',
            'value': alerts['active'],
            'supporting': f'{alerts["critical"]} critical · {alerts["verification_pending"]} verify',
            'icon': 'triangle-alert',
            'tone': 'critical' if alerts['critical'] else ('warning' if alerts['verification_pending'] else ('info' if alerts['active'] else 'normal')),
            'status': 'Critical' if alerts['critical'] else ('Verify' if alerts['verification_pending'] else ('Active' if alerts['active'] else 'Clear')),
        },
        {
            'label': 'Delivery Failures',
            'value': alerts['delivery_failures'],
            'supporting': f'{alerts["silenced"]} active delivery silences',
            'icon': 'send-horizontal',
            'tone': 'warning' if alerts['delivery_failures'] else 'normal',
            'status': 'Failed' if alerts['delivery_failures'] else 'Clear',
        },
        {
            'label': 'Pending Governance',
            'value': automation['pending_governance'],
            'supporting': f'{automation["failures"]} execution failures',
            'icon': 'workflow',
            'tone': 'warning' if automation['pending_governance'] or automation['failures'] else 'normal',
            'status': 'Review' if automation['pending_governance'] or automation['failures'] else 'Clear',
        },
    ]


def _coverage_metrics(
    *,
    summary: dict[str, int],
    assets: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            'label': 'Managed Assets',
            'value': summary['registered_assets'],
            'supporting': f'{assets["kubernetes"]} Kubernetes · {assets["object_storage"]} Object Storage',
        },
        {
            'label': 'Rule Coverage',
            'value': f'{summary["available_rules"]}/{summary["catalog_rules"]}',
            'supporting': f'{summary["reserved_rules"]} reserved · {summary["imported_rules"]} imported',
        },
        {
            'label': 'Resolved in 24h',
            'value': alerts['resolved_24h'],
            'supporting': f'{alerts["postmortem_required"]} postmortem pending',
        },
        {
            'label': 'Published Runbooks',
            'value': automation['published_runbooks'],
            'supporting': automation['execution_label'],
        },
    ]


def _workspace_rows(
    *,
    summary: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = summary['findings']
    critical = summary['critical']
    warning = summary['warning']
    recommendation_tone = 'critical' if critical else ('warning' if warning else ('info' if findings else 'normal'))
    recommendation_status = (
        f'{critical} Critical'
        if critical
        else (f'{warning} Warning' if warning else (f'{findings} Active' if findings else 'Clear'))
    )
    alert_tone = 'critical' if alerts['critical'] else ('warning' if alerts['verification_pending'] else ('info' if alerts['active'] else 'normal'))
    alert_status = (
        f'{alerts["critical"]} Critical'
        if alerts['critical']
        else (f'{alerts["verification_pending"]} Verify' if alerts['verification_pending'] else (f'{alerts["active"]} Active' if alerts['active'] else 'Clear'))
    )

    return [
        {
            'key': 'recommendations',
            'title': 'Recommendations',
            'description': 'Prioritized findings, affected assets, measured evidence, and operator remediation guidance.',
            'icon': 'sparkles',
            'status': recommendation_status,
            'tone': recommendation_tone,
            'metric': findings,
            'metric_label': 'active findings',
            'supporting': f'{summary["active_domains"]} active domains',
            'href_endpoint': 'intelligence.recommendations',
            'action_label': 'Review Recommendations',
        },
        {
            'key': 'alerts',
            'title': 'Alert Intelligence',
            'description': 'Own alert acknowledgement, routing, delivery silence, resolution evidence, history, and postmortem workflow.',
            'icon': 'siren',
            'status': alert_status,
            'tone': alert_tone,
            'metric': alerts['active'],
            'metric_label': 'active cases',
            'supporting': f'{alerts["resolved_24h"]} resolved in 24h',
            'href_endpoint': 'alert_intelligence.index',
            'action_label': 'Open Alert Operations',
        },
        {
            'key': 'catalog',
            'title': 'Rule Catalog',
            'description': 'Canonical detection definitions, evidence boundaries, severity ownership, and operator-response contracts.',
            'icon': 'list-checks',
            'status': f'{summary["available_rules"]} Available',
            'tone': 'normal' if summary['available_rules'] else 'unknown',
            'metric': summary['catalog_rules'],
            'metric_label': 'catalog rules',
            'supporting': f'{summary["reserved_rules"]} reserved plan',
            'href_endpoint': 'intelligence.catalog',
            'action_label': 'Open Rule Catalog',
        },
        {
            'key': 'automation',
            'title': 'Automation Control',
            'description': 'Govern runbooks, approvals, execution readiness, verification, recovery, and operator accountability.',
            'icon': 'workflow',
            'status': str(automation['posture']['label']),
            'tone': str(automation['posture']['tone']),
            'metric': automation['pending_governance'],
            'metric_label': 'pending governance',
            'supporting': f'{automation["published_runbooks"]} published runbooks',
            'href_endpoint': 'automation_control.index',
            'action_label': 'Open Automation Control',
        },
    ]
