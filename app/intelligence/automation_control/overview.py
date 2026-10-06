from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.extensions.db import db
from app.intelligence.automation_control.notifications import DECISION_NOTIFICATION_EVENTS
from app.intelligence.resolver.notifications import EXECUTION_NOTIFICATION_EVENTS
from app.intelligence.resolver.production_readiness import ProductionReadinessError, assess_readiness
from app.models.intelligence import (
    IntelligenceDecision,
    IntelligenceDecisionCandidate,
    IntelligenceExecutionJournal,
)
from app.models.knowledge import KnowledgeRunbookAlertBinding, KnowledgeRunbookRevision
from app.models.notification_channel import NotificationChannel
from app.models.resolver import (
    ResolverDeploymentPolicy,
    ResolverOperationalControl,
    ResolverProductionReadinessRecord,
)


def build_automation_overview(*, execution_enabled: bool, registry_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    global_control = ResolverOperationalControl.query.filter_by(cluster_id=None).one_or_none()
    readiness_records = ResolverProductionReadinessRecord.query.order_by(
        ResolverProductionReadinessRecord.updated_at.desc(),
        ResolverProductionReadinessRecord.id.desc(),
    ).all()
    readiness_complete = sum(1 for record in readiness_records if _readiness_complete(record))
    readiness_production = sum(
        1 for record in readiness_records if record.rollout_stage == 'production' and _readiness_complete(record)
    )
    readiness_total = len(readiness_records)

    pending_candidates = IntelligenceDecisionCandidate.query.filter_by(review_status='pending').count()
    awaiting_approval = IntelligenceDecision.query.filter_by(workflow_status='pending_approval').count()
    approved_waiting = IntelligenceDecision.query.filter(
        IntelligenceDecision.workflow_status.in_(('ready', 'approved'))
    ).count()
    running = IntelligenceExecutionJournal.query.filter(
        IntelligenceExecutionJournal.orchestration_status.in_(('queued', 'running', 'retry_wait'))
    ).count()
    failures = IntelligenceExecutionJournal.query.filter(
        db.or_(
            IntelligenceExecutionJournal.orchestration_status == 'dead_letter',
            IntelligenceExecutionJournal.status == 'failed',
        )
    ).count()
    verification_states = [
        str(((row.result_json or {}).get('verification') or {}).get('status') or '')
        for row in IntelligenceExecutionJournal.query.filter_by(status='succeeded').all()
    ]
    verification_verified = sum(state == 'verified' for state in verification_states)
    verification_pending = sum(state == 'pending' for state in verification_states)
    verification_failed = sum(state == 'failed' for state in verification_states)
    failures += verification_failed
    active_policies = ResolverDeploymentPolicy.query.filter_by(lifecycle_status='active').count()
    published_runbooks = KnowledgeRunbookRevision.query.filter_by(publication_status='published').count()
    active_bindings = KnowledgeRunbookAlertBinding.query.filter_by(lifecycle_status='active').count()
    notification = _notification_readiness()

    kill_switch = bool(global_control and global_control.global_kill_switch)
    maintenance = bool(global_control and global_control.maintenance_mode)
    readiness = _readiness_posture(readiness_complete, readiness_production, readiness_total)
    posture = _control_posture(
        execution_enabled=execution_enabled,
        kill_switch=kill_switch,
        maintenance=maintenance,
        readiness_production=readiness_production,
        readiness_total=readiness_total,
    )

    counts = {
        'pending_candidates': pending_candidates,
        'awaiting_approval': awaiting_approval,
        'approved_waiting': approved_waiting,
        'running': running,
        'failures': failures,
        'verification_verified': verification_verified,
        'verification_pending': verification_pending,
        'verification_failed': verification_failed,
        'active_policies': active_policies,
        'published_runbooks': published_runbooks,
        'active_bindings': active_bindings,
        'registered_actions': len(registry_rows),
        'readiness_complete': readiness_complete,
        'readiness_production': readiness_production,
        'readiness_total': readiness_total,
    }

    return {
        'posture': posture,
        'execution': {
            'enabled': execution_enabled,
            'label': 'Enabled' if execution_enabled else 'Disabled',
            'tone': 'warning' if execution_enabled else 'unknown',
            'helper': (
                'Infrastructure execution may proceed only after every downstream admission gate passes.'
                if execution_enabled
                else 'Governance stays writable while infrastructure execution remains fail-closed.'
            ),
        },
        'guardrails': {
            'kill_switch': {
                'label': 'Active' if kill_switch else 'Clear',
                'tone': 'critical' if kill_switch else 'normal',
                'helper': 'Global resolver kill switch blocks new execution.'
                if kill_switch
                else 'No global kill switch is active.',
            },
            'maintenance': {
                'label': 'Maintenance' if maintenance else 'Normal',
                'tone': 'maintenance' if maintenance else 'normal',
                'helper': 'Resolver maintenance mode blocks execution.'
                if maintenance
                else 'Resolver maintenance mode is not active.',
            },
            'readiness': readiness,
            'notifications': notification,
        },
        'counts': counts,
        'pipeline': _pipeline_rows(counts=counts, execution_enabled=execution_enabled),
        'pilot': _pilot_posture(registry_rows),
    }


def _readiness_complete(record: ResolverProductionReadinessRecord) -> bool:
    try:
        return bool(assess_readiness(results=record.validation_results_json, rollout_stage=record.rollout_stage).ready)
    except ProductionReadinessError:
        return False


def _readiness_posture(complete: int, production: int, total: int) -> dict[str, str | int]:
    if total == 0:
        return {
            'label': 'Not Assessed',
            'tone': 'unknown',
            'helper': 'No resolver action has recorded production-readiness evidence.',
            'complete': 0,
            'production': 0,
            'total': 0,
        }
    if production == total:
        return {
            'label': 'Production Ready',
            'tone': 'normal',
            'helper': f'{production} of {total} readiness records are complete and staged for production.',
            'complete': complete,
            'production': production,
            'total': total,
        }
    if complete == total:
        return {
            'label': 'Evidence Complete',
            'tone': 'info',
            'helper': f'All {total} readiness records have complete checks, but not all are staged for production.',
            'complete': complete,
            'production': production,
            'total': total,
        }
    return {
        'label': 'Review Required',
        'tone': 'warning',
        'helper': f'{complete} of {total} readiness records currently have complete validation evidence.',
        'complete': complete,
        'production': production,
        'total': total,
    }


def _control_posture(
    *,
    execution_enabled: bool,
    kill_switch: bool,
    maintenance: bool,
    readiness_production: int,
    readiness_total: int,
) -> dict[str, str]:
    if kill_switch:
        return {
            'label': 'Kill Switch Active',
            'tone': 'critical',
            'helper': 'The global resolver kill switch blocks new execution.',
        }
    if maintenance:
        return {
            'label': 'Maintenance',
            'tone': 'maintenance',
            'helper': 'Resolver maintenance mode blocks new execution.',
        }
    if not execution_enabled:
        return {
            'label': 'Governance Only',
            'tone': 'info',
            'helper': 'KAORI exposes decision, readiness, and safety evidence while infrastructure execution remains disabled.',
        }
    if readiness_total == 0 or readiness_production < readiness_total:
        return {
            'label': 'Execution Gated',
            'tone': 'warning',
            'helper': 'Execution is enabled, but production-readiness evidence is incomplete.',
        }
    return {
        'label': 'Controlled Execution',
        'tone': 'normal',
        'helper': 'The execution gate and recorded readiness currently allow controlled resolver paths.',
    }


def _notification_readiness() -> dict[str, str | int]:
    channels = NotificationChannel.query.filter(
        NotificationChannel.enabled.is_(True),
        NotificationChannel.test_status == 'success',
    ).all()
    required = set((*DECISION_NOTIFICATION_EVENTS, *EXECUTION_NOTIFICATION_EVENTS))
    covered: set[str] = set()
    for channel in channels:
        covered.update(required.intersection(set(channel.event_types or [])))
    missing = sorted(required - covered)
    operational = [
        channel
        for channel in channels
        if channel.last_delivery_status == 'success' and required.intersection(set(channel.event_types or []))
    ]
    if not missing and operational:
        return {
            'label': 'Operational',
            'tone': 'normal',
            'helper': (
                f'All {len(required)} lifecycle events are covered; '
                f'{len(operational)} channel(s) have delivery evidence.'
            ),
            'eligible': len(channels),
            'operational': len(operational),
        }
    if not missing:
        return {
            'label': 'Ready',
            'tone': 'info',
            'helper': f'All {len(required)} Automation Control lifecycle events are covered by validated channels.',
            'eligible': len(channels),
            'operational': 0,
        }
    return {
        'label': 'Coverage Incomplete' if channels else 'Not Configured',
        'tone': 'warning' if channels else 'unknown',
        'helper': (
            f'{len(missing)} lifecycle event(s) still lack a validated Notification Channel: {", ".join(missing)}.'
            if channels
            else 'No validated Notification Channel currently covers Automation Control lifecycle events.'
        ),
        'eligible': len(channels),
        'operational': len(operational),
    }


def _pipeline_rows(*, counts: dict[str, int], execution_enabled: bool) -> list[dict[str, str]]:
    published_runbooks = counts['published_runbooks']
    active_bindings = counts['active_bindings']
    pending_candidates = counts['pending_candidates']
    awaiting_approval = counts['awaiting_approval']
    approved_waiting = counts['approved_waiting']
    running = counts['running']
    verification_verified = counts['verification_verified']
    verification_pending = counts['verification_pending']
    verification_failed = counts['verification_failed']
    return [
        {
            'number': '1',
            'key': 'evidence',
            'label': 'Evidence',
            'icon': 'database',
            'status': 'Available',
            'tone': 'normal',
            'description': 'Recommendations and alert evidence remain the authoritative input to governed automation.',
        },
        {
            'number': '2',
            'key': 'runbook',
            'label': 'Runbook Match',
            'icon': 'book-open-check',
            'status': f'{published_runbooks} Published' if published_runbooks else 'No Published Runbooks',
            'tone': 'normal' if published_runbooks and active_bindings else 'warning',
            'description': f'{active_bindings} active deterministic binding(s) currently connect evidence to published runbooks.',
        },
        {
            'number': '3',
            'key': 'candidate',
            'label': 'Decision Candidate',
            'icon': 'clipboard-clock',
            'status': f'{pending_candidates} Pending' if pending_candidates else 'Queue Clear',
            'tone': 'warning' if pending_candidates else 'normal',
            'description': 'Candidates remain non-executable until reviewed and promoted into immutable decision evidence.',
        },
        {
            'number': '4',
            'key': 'approval',
            'label': 'Decision & Approval',
            'icon': 'badge-check',
            'status': f'{awaiting_approval} Awaiting' if awaiting_approval else f'{approved_waiting} Approved',
            'tone': 'warning' if awaiting_approval else ('info' if approved_waiting else 'normal'),
            'description': 'Policy outcome, approval requirement, scope, and expiry stay bound to immutable evidence.',
        },
        {
            'number': '5',
            'key': 'execution',
            'label': 'Controlled Execution',
            'icon': 'server-cog',
            'status': f'{running} Active' if running else ('Enabled' if execution_enabled else 'Execution Disabled'),
            'tone': 'warning' if running or execution_enabled else 'unknown',
            'description': 'Only registered, allowlisted resolver actions may cross the execution boundary after all gates pass.',
        },
        {
            'number': '6',
            'key': 'verification',
            'label': 'Verification',
            'icon': 'circle-check',
            'status': (
                f'{verification_failed} Failed'
                if verification_failed
                else (
                    f'{verification_pending} Pending' if verification_pending else f'{verification_verified} Verified'
                )
            ),
            'tone': 'critical' if verification_failed else ('warning' if verification_pending else 'normal'),
            'description': 'API mutation success is not remediation success; workload health is verified as a separate auditable outcome.',
        },
    ]


def _pilot_posture(registry_rows: Sequence[dict[str, Any]]) -> dict[str, str]:
    action_key = 'kubernetes.deployment.restart'
    registered = any(str(row.get('action_key') or '') == action_key for row in registry_rows)
    return {
        'action_key': action_key,
        'label': 'Registered · Execution Default-Deny' if registered else 'Not Registered',
        'tone': 'info' if registered else 'unknown',
        'helper': (
            'Kubernetes Deployment restart remains the intended first controlled execution pilot; approval, allowlist, dry-run, post-action verification, and recovery evidence remain mandatory.'
            if registered
            else 'The intended Kubernetes Deployment restart pilot is not present in the active resolver registry.'
        ),
    }
