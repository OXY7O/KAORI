from __future__ import annotations

from typing import Any

from app.integrations.delivery.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.integrations.delivery.notification_channels.service import dispatch_matching_notification_event
from app.models.intelligence import IntelligenceDecision, IntelligenceExecutionJournal

EXECUTION_STARTED_EVENT = 'automation.execution_started'
EXECUTION_COMPLETED_EVENT = 'automation.execution_completed'
EXECUTION_FAILED_EVENT = 'automation.execution_failed'
VERIFICATION_FAILED_EVENT = 'automation.verification_failed'
EXECUTION_NOTIFICATION_EVENTS = (
    EXECUTION_STARTED_EVENT,
    EXECUTION_COMPLETED_EVENT,
    EXECUTION_FAILED_EVENT,
    VERIFICATION_FAILED_EVENT,
)


def dispatch_execution_notification(
    journal: IntelligenceExecutionJournal,
    *,
    event_type: str,
    base_url: str = '',
) -> dict[str, Any]:
    event = build_execution_notification_event(journal, event_type=event_type, base_url=base_url)
    return dispatch_matching_notification_event(event=event)


def build_execution_notification_event(
    journal: IntelligenceExecutionJournal,
    *,
    event_type: str,
    base_url: str = '',
) -> NotificationEvent:
    if event_type not in EXECUTION_NOTIFICATION_EVENTS:
        raise ValueError(f'Unsupported resolver execution notification event: {event_type}.')
    decision = journal.decision
    verification = dict((journal.result_json or {}).get('verification') or {})
    messages = {
        EXECUTION_STARTED_EVENT: (
            'Execution Started',
            'info',
            'The authorized resolver job crossed the execution boundary and started processing.',
        ),
        EXECUTION_COMPLETED_EVENT: (
            'Execution Verified',
            'info',
            'The resolver action completed and post-action remediation verification passed.',
        ),
        EXECUTION_FAILED_EVENT: (
            'Execution Failed',
            'critical',
            journal.error_message or 'The resolver action failed before remediation verification could pass.',
        ),
        VERIFICATION_FAILED_EVENT: (
            'Verification Failed',
            'critical',
            str(verification.get('summary') or journal.error_message or 'Post-action verification failed.'),
        ),
    }
    label, severity, headline = messages[event_type]
    body = '\n'.join(
        (
            headline,
            f'Action: {decision.action_key}',
            f'Scope: {_scope_label(decision)}',
            f'Execution: {journal.public_id}',
            f'Orchestration: {journal.orchestration_status}',
            f'Verification: {verification.get("status") or "pending"}',
        )
    )
    return NotificationEvent(
        event_type=event_type,
        domain=_decision_domain(decision),
        asset_type='automation_execution',
        asset_key=journal.public_id,
        severity=severity,
        event_key=f'{event_type}:{journal.public_id}',
        message=NotificationMessage(
            title=f'{label} · {decision.action_key}',
            body=body,
            severity=severity,
            action_url=_execution_action_url(base_url),
            action_label='Open Execution Control',
        ),
        payload={
            'decision_id': decision.public_id,
            'execution_journal_id': journal.public_id,
            'action_key': decision.action_key,
            'cluster_id': decision.cluster_id,
            'namespace': decision.namespace,
            'execution_status': journal.status,
            'orchestration_status': journal.orchestration_status,
            'verification_status': verification.get('status'),
            'evidence_hash': journal.evidence_hash,
        },
    )


def _decision_domain(decision: IntelligenceDecision) -> str:
    action_key = str(decision.action_key or '').strip().lower()
    if action_key.startswith('object_storage.'):
        return 'object_storage'
    if action_key.startswith('kubernetes.'):
        return 'kubernetes'
    raise ValueError(f'Unsupported resolver execution domain for action: {decision.action_key}.')


def _scope_label(decision: IntelligenceDecision) -> str:
    cluster = str(decision.cluster_id or 'global')
    namespace = str(decision.namespace or 'all namespaces')
    return f'{cluster} / {namespace}'


def _execution_action_url(base_url: str) -> str:
    path = '/intelligence/automation-control?workspace=operations'
    normalized = str(base_url or '').strip().rstrip('/')
    return f'{normalized}{path}' if normalized else path
