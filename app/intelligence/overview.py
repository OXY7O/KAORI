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
        summary=summary,
        alerts=alerts,
        automation=automation,
    )

    return {
        'posture': posture,
        'summary': summary,
        'assets': assets,
        'alerts': alerts,
        'automation': automation,
        'kpi_cards': _kpi_cards(summary=summary, alerts=alerts, automation=automation),
        'posture_items': _posture_items(summary=summary, alerts=alerts, automation=automation),
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
    summary: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> dict[str, str]:
    critical_total = summary['critical'] + alerts['critical']
    if critical_total:
        return {
            'label': 'Critical Review',
            'tone': 'critical',
            'helper': (
                f'{critical_total} critical intelligence signal(s) require immediate operator review '
                'across Recommendations and Alert Operations.'
            ),
        }
    if alerts['delivery_failures'] or automation['failures']:
        return {
            'label': 'Control Attention',
            'tone': 'warning',
            'helper': (
                f'{alerts["delivery_failures"] + automation["failures"]} delivery or automation control failure(s) '
                'require operational review.'
            ),
        }
    if summary['warning'] or alerts['verification_pending'] or automation['pending_governance']:
        return {
            'label': 'Review Required',
            'tone': 'warning',
            'helper': (
                'Warnings, verification-pending alert cases, or governed automation decisions '
                'currently require operator attention.'
            ),
        }
    if summary['findings'] or alerts['active']:
        return {
            'label': 'Active Intelligence',
            'tone': 'info',
            'helper': (
                f'{summary["findings"]} recommendation finding(s) and {alerts["active"]} active alert case(s) '
                'are available for operational review.'
            ),
        }
    if summary['registered_assets'] == 0:
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


def _kpi_cards(
    *,
    summary: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            'label': 'Active Findings',
            'value': summary['findings'],
            'supporting': f'{summary["critical"]} critical · {summary["warning"]} warning',
            'icon': 'sparkles',
            'tone': 'critical' if summary['critical'] else ('warning' if summary['warning'] else 'normal'),
            'href_endpoint': 'intelligence.recommendations',
            'action_label': 'View Recommendations',
        },
        {
            'label': 'Active Alerts',
            'value': alerts['active'],
            'supporting': f'{alerts["critical"]} critical · {alerts["verification_pending"]} verify',
            'icon': 'bell-ring',
            'tone': (
                'critical'
                if alerts['critical']
                else ('warning' if alerts['verification_pending'] else ('info' if alerts['active'] else 'normal'))
            ),
            'href_endpoint': 'alert_intelligence.index',
            'action_label': 'View Alert Intelligence',
        },
        {
            'label': 'Rule Coverage',
            'value': f'{summary["available_rules"]} / {summary["catalog_rules"]}',
            'supporting': f'{summary["reserved_rules"]} reserved · {summary["imported_rules"]} imported',
            'icon': 'panels-top-left',
            'tone': 'info' if summary['catalog_rules'] else 'unknown',
            'href_endpoint': 'intelligence.catalog',
            'action_label': 'View Rule Catalog',
        },
        {
            'label': 'Pending Governance',
            'value': automation['pending_governance'],
            'supporting': f'{automation["failures"]} execution failures',
            'icon': 'zap',
            'tone': 'warning' if automation['pending_governance'] or automation['failures'] else 'normal',
            'href_endpoint': 'automation_control.index',
            'action_label': 'View Automation Control',
        },
    ]


def _posture_items(
    *,
    summary: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    critical_total = summary['critical'] + alerts['critical']
    return [
        {
            'label': 'Critical Attention',
            'value': f'{summary["critical"]} recommendations · {alerts["critical"]} critical alerts',
            'supporting': (
                f'{critical_total} critical intelligence signal(s) need immediate review.'
                if critical_total
                else 'No critical intelligence signal requires immediate review.'
            ),
            'icon': 'circle-dot-dashed',
            'tone': 'critical' if critical_total else 'normal',
            'href_endpoint': 'intelligence.recommendations' if summary['critical'] else 'alert_intelligence.index',
        },
        {
            'label': 'Evidence Freshness',
            'value': 'Committed State',
            'supporting': 'Overview is database-backed; provider collection and refresh stay worker-owned.',
            'icon': 'shield-check',
            'tone': 'info',
            'href_endpoint': 'alert_intelligence.index',
        },
        {
            'label': 'Automation Readiness',
            'value': f'{automation["pending_governance"]} decisions awaiting governance',
            'supporting': (
                f'{automation["failures"]} execution failure(s) also require review.'
                if automation['failures']
                else automation['execution_label']
            ),
            'icon': 'circle-check-big',
            'tone': 'warning' if automation['pending_governance'] or automation['failures'] else 'normal',
            'href_endpoint': 'automation_control.index',
        },
    ]


def _workspace_rows(
    *,
    summary: dict[str, int],
    alerts: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            'key': 'recommendations',
            'title': 'Recommendations',
            'description': 'Prioritized findings with affected assets, evidence, and remediation guidance.',
            'icon': 'sparkles',
            'tone': 'critical' if summary['critical'] else ('warning' if summary['warning'] else 'info'),
            'primary_value': summary['findings'],
            'primary_label': 'active',
            'secondary_value': summary['critical'],
            'secondary_label': 'critical',
            'href_endpoint': 'intelligence.recommendations',
        },
        {
            'key': 'alerts',
            'title': 'Alert Intelligence',
            'description': 'Alert cases, acknowledgement, routing, silences, resolution evidence, and history.',
            'icon': 'bell-ring',
            'tone': 'critical' if alerts['critical'] else ('warning' if alerts['verification_pending'] else 'info'),
            'primary_value': alerts['active'],
            'primary_label': 'active',
            'secondary_value': alerts['verification_pending'],
            'secondary_label': 'verify',
            'href_endpoint': 'alert_intelligence.index',
        },
        {
            'key': 'catalog',
            'title': 'Rule Catalog',
            'description': 'Detection and validation rules available across managed Intelligence domains.',
            'icon': 'panels-top-left',
            'tone': 'info',
            'primary_value': summary['catalog_rules'],
            'primary_label': 'total rules',
            'secondary_value': summary['available_rules'],
            'secondary_label': 'available',
            'href_endpoint': 'intelligence.catalog',
        },
        {
            'key': 'automation',
            'title': 'Automation Control',
            'description': 'Automation decisions, approvals, execution readiness, verification, and recovery.',
            'icon': 'settings-2',
            'tone': 'warning' if automation['pending_governance'] or automation['failures'] else 'normal',
            'primary_value': automation['pending_governance'],
            'primary_label': 'pending',
            'secondary_value': automation['published_runbooks'],
            'secondary_label': 'runbooks',
            'href_endpoint': 'automation_control.index',
        },
    ]

