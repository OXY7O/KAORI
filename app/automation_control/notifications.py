from __future__ import annotations

from typing import Any

from app.models.intelligence import IntelligenceDecision
from app.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.notification_channels.service import dispatch_matching_notification_event

APPROVAL_REQUIRED_EVENT = 'automation.approval_required'
DECISION_APPROVED_EVENT = 'automation.decision_approved'
DECISION_REJECTED_EVENT = 'automation.decision_rejected'
DECISION_NOTIFICATION_EVENTS = (
    APPROVAL_REQUIRED_EVENT,
    DECISION_APPROVED_EVENT,
    DECISION_REJECTED_EVENT,
)


def dispatch_decision_notification(
    decision: IntelligenceDecision,
    *,
    event_type: str,
    base_url: str = '',
) -> dict[str, Any]:
    event = build_decision_notification_event(decision, event_type=event_type, base_url=base_url)
    return dispatch_matching_notification_event(event=event)


def build_decision_notification_event(
    decision: IntelligenceDecision,
    *,
    event_type: str,
    base_url: str = '',
) -> NotificationEvent:
    if event_type not in DECISION_NOTIFICATION_EVENTS:
        raise ValueError(f'Unsupported Automation Control decision notification event: {event_type}.')
    domain = _decision_domain(decision)
    action_url = _action_url(base_url)
    approval = decision.approvals[0] if decision.approvals else None

    if event_type == APPROVAL_REQUIRED_EVENT:
        title = f'Approval Required · {decision.action_key}'
        severity = _decision_severity(decision)
        body = _decision_body(
            decision,
            headline='A governed automation decision is awaiting accountable approval.',
            extra=f'Policy: {decision.policy_reason}',
        )
        action_label = 'Review Decision'
    elif event_type == DECISION_APPROVED_EVENT:
        title = f'Decision Approved · {decision.action_key}'
        severity = 'info'
        body = _decision_body(
            decision,
            headline='The governed automation decision was approved.',
            extra=(
                f'Review note: {approval.reason}'
                if approval and approval.reason
                else 'Review note: No approval note recorded.'
            ),
        )
        action_label = 'Review Approval'
    else:
        title = f'Decision Rejected · {decision.action_key}'
        severity = 'warning'
        body = _decision_body(
            decision,
            headline='The governed automation decision was rejected and is not execution-eligible.',
            extra=(
                f'Rejection reason: {approval.reason}'
                if approval and approval.reason
                else 'Rejection reason: Not recorded.'
            ),
        )
        action_label = 'Review Rejection'

    return NotificationEvent(
        event_type=event_type,
        domain=domain,
        asset_type='automation_decision',
        asset_key=decision.public_id,
        severity=severity,
        event_key=f'{event_type}:{decision.public_id}',
        message=NotificationMessage(
            title=title,
            body=body,
            severity=severity,
            action_url=action_url,
            action_label=action_label,
        ),
        payload={
            'decision_id': decision.public_id,
            'rule_key': decision.rule_key,
            'action_key': decision.action_key,
            'runbook_key': decision.runbook_key,
            'cluster_id': decision.cluster_id,
            'namespace': decision.namespace,
            'policy_outcome': decision.policy_outcome,
            'approval_required': decision.approval_required,
            'workflow_status': decision.workflow_status,
            'evidence_hash': decision.evidence_hash,
        },
    )


def _decision_domain(decision: IntelligenceDecision) -> str:
    action_key = str(decision.action_key or '').strip().lower()
    if action_key.startswith('object_storage.'):
        return 'object_storage'
    if action_key.startswith('kubernetes.'):
        return 'kubernetes'
    raise ValueError(f'Unsupported Automation Control decision domain for action: {decision.action_key}.')


def _decision_severity(decision: IntelligenceDecision) -> str:
    value = str(decision.severity or 'info').strip().lower()
    return value if value in {'critical', 'warning', 'info'} else 'info'


def _decision_body(decision: IntelligenceDecision, *, headline: str, extra: str) -> str:
    return '\n'.join(
        (
            headline,
            f'Action: {decision.action_key}',
            f'Rule: {decision.rule_key}',
            f'Runbook: {decision.runbook_key or "-"}',
            f'Scope: {_scope_label(decision)}',
            f'Severity: {_decision_severity(decision).title()}',
            f'Expires: {decision.expires_at.isoformat()}',
            extra,
            'Infrastructure mutation remains governed by the independent Automation Control execution gate.',
        )
    )


def _scope_label(decision: IntelligenceDecision) -> str:
    cluster = str(decision.cluster_id or 'global')
    namespace = str(decision.namespace or 'all namespaces')
    return f'{cluster} / {namespace}'


def _action_url(base_url: str) -> str:
    path = '/intelligence/automation-control?workspace=decisions'
    normalized = str(base_url or '').strip().rstrip('/')
    return f'{normalized}{path}' if normalized else path
