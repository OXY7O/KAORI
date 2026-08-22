from __future__ import annotations

from typing import Any

from app.common.automation_execution import execution_enabled
from app.extensions.db import db
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.rule_presentation import normalize_rule
from app.intelligence.service import get_active_recommendation_findings
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceDecision, IntelligenceDecisionCandidate, IntelligenceExecutionJournal
from app.models.knowledge import KnowledgeRunbookRevision
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
        critical=critical,
        warning=warning,
        findings=len(findings),
        automation_failures=automation['failures'],
        pending_automation=automation['pending_governance'],
    )

    return {
        'posture': posture,
        'summary': summary,
        'assets': assets,
        'automation': automation,
        'overview_cards': _overview_cards(
            summary=summary,
            assets=assets,
            automation=automation,
        ),
        'capabilities': _capability_rows(summary=summary, automation=automation),
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


def _overview_posture(
    *,
    registered_assets: int,
    critical: int,
    warning: int,
    findings: int,
    automation_failures: int,
    pending_automation: int,
) -> dict[str, str]:
    if critical:
        return {
            'label': 'Critical Review',
            'tone': 'critical',
            'helper': f'{critical} critical recommendation finding(s) require immediate review.',
        }
    if automation_failures:
        return {
            'label': 'Control Attention',
            'tone': 'warning',
            'helper': f'{automation_failures} automation execution or verification failure(s) require review.',
        }
    if warning or pending_automation:
        return {
            'label': 'Review Required',
            'tone': 'warning',
            'helper': 'Operational findings or governed automation decisions currently require operator attention.',
        }
    if findings:
        return {
            'label': 'Active Findings',
            'tone': 'info',
            'helper': f'{findings} active recommendation finding(s) are available for review.',
        }
    if registered_assets == 0:
        return {
            'label': 'No Managed Assets',
            'tone': 'unknown',
            'helper': (
                'Rule and automation governance remain visible, but no managed infrastructure asset is registered yet.'
            ),
        }
    return {
        'label': 'No Active Findings',
        'tone': 'normal',
        'helper': 'No current catalog-backed recommendation finding requires operator action.',
    }


def _overview_cards(
    *,
    summary: dict[str, int],
    assets: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = summary['findings']
    critical = summary['critical']
    warning = summary['warning']
    return [
        {
            'key': 'recommendations',
            'title': 'Recommendations',
            'icon': 'sparkles',
            'metric_label': 'Active Findings',
            'metric_value': findings,
            'details': [
                {'label': 'Critical', 'value': critical},
                {'label': 'Warning', 'value': warning},
                {'label': 'Active Domains', 'value': summary['active_domains']},
            ],
        },
        {
            'key': 'coverage',
            'title': 'Managed Coverage',
            'icon': 'boxes',
            'metric_label': 'Managed Assets',
            'metric_value': summary['registered_assets'],
            'details': [
                {'label': 'Kubernetes', 'value': assets['kubernetes']},
                {'label': 'Object Storage', 'value': assets['object_storage']},
                {'label': 'Supported Domains', 'value': summary['available_domains']},
            ],
        },
        {
            'key': 'catalog',
            'title': 'Rule Catalog',
            'icon': 'list-checks',
            'metric_label': 'Catalog Rules',
            'metric_value': summary['catalog_rules'],
            'details': [
                {'label': 'Available', 'value': summary['available_rules']},
                {'label': 'Reserved', 'value': summary['reserved_rules']},
                {'label': 'Imported Signals', 'value': summary['imported_rules']},
            ],
        },
        {
            'key': 'automation',
            'title': 'Automation Control',
            'icon': 'workflow',
            'metric_label': 'Pending Governance',
            'metric_value': automation['pending_governance'],
            'details': [
                {'label': 'Awaiting Approval', 'value': automation['awaiting_approval']},
                {'label': 'Execution Failures', 'value': automation['failures']},
                {'label': 'Published Runbooks', 'value': automation['published_runbooks']},
            ],
        },
    ]


def _capability_rows(
    *,
    summary: dict[str, int],
    automation: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = summary['findings']
    critical = summary['critical']
    warning = summary['warning']
    recommendation_tone = 'critical' if critical else ('warning' if warning else ('info' if findings else 'normal'))
    recommendation_status = (
        f'{critical} Critical'
        if critical
        else (f'{warning} Warning' if warning else (f'{findings} Active' if findings else 'No Active Findings'))
    )
    registered_assets = summary['registered_assets']
    alert_status = f'{registered_assets} Registered Assets' if registered_assets else 'No Managed Assets'
    alert_tone = 'info' if registered_assets else 'unknown'

    return [
        {
            'key': 'recommendations',
            'title': 'Recommendations',
            'eyebrow': 'Evidence-Backed Guidance',
            'description': 'Review prioritized findings derived from committed Kubernetes and Object Storage evidence.',
            'icon': 'sparkles',
            'status': recommendation_status,
            'tone': recommendation_tone,
            'metric_label': 'Active Findings',
            'metric_value': findings,
            'supporting': f'{critical} critical · {warning} warning',
            'href_endpoint': 'intelligence.recommendations',
            'action_label': 'Open Recommendations',
        },
        {
            'key': 'alerts',
            'title': 'Alert Intelligence',
            'eyebrow': 'Provider Alert Context',
            'description': (
                'Correlate provider alerts with asset identity, recommendations, rule guidance, '
                'and notification evidence on demand.'
            ),
            'icon': 'triangle-alert',
            'status': alert_status,
            'tone': alert_tone,
            'metric_label': 'Supported Domains',
            'metric_value': summary['available_domains'],
            'supporting': 'Kubernetes + Object Storage',
            'href_endpoint': 'alert_intelligence.index',
            'action_label': 'Open Alert Intelligence',
        },
        {
            'key': 'catalog',
            'title': 'Rule Catalog',
            'eyebrow': 'Canonical Definitions',
            'description': (
                'Review detection ownership, evidence boundaries, provider coverage, severity, '
                'and operator-response definitions.'
            ),
            'icon': 'list-checks',
            'status': f'{summary["available_rules"]} Available',
            'tone': 'normal' if summary['available_rules'] else 'unknown',
            'metric_label': 'Catalog Rules',
            'metric_value': summary['catalog_rules'],
            'supporting': f'{summary["reserved_rules"]} reserved plan',
            'href_endpoint': 'intelligence.catalog',
            'action_label': 'Open Rule Catalog',
        },
        {
            'key': 'automation',
            'title': 'Automation Control',
            'eyebrow': 'Governed Remediation',
            'description': (
                'Review system runbooks, decision evidence, approvals, execution readiness, '
                'verification, and recovery controls.'
            ),
            'icon': 'workflow',
            'status': str(automation['posture']['label']),
            'tone': str(automation['posture']['tone']),
            'metric_label': 'Pending Governance',
            'metric_value': automation['pending_governance'],
            'supporting': str(automation['execution_label']),
            'href_endpoint': 'automation_control.index',
            'action_label': 'Open Automation Control',
        },
    ]
