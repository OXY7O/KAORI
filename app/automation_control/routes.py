from __future__ import annotations

import json
from collections.abc import Callable, Collection
from typing import Any

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.automation_control.presentation import build_automation_control_context, upsert_deployment_policy
from app.extensions.db import db
from app.integrations.resolver_bootstrap import get_resolver_registry
from app.intelligence.workflow import approve_decision, reject_decision
from app.knowledge.candidate_review import dismiss_candidate, promote_candidate
from app.knowledge.matching import create_alert_binding
from app.knowledge.service import (
    create_revision,
    create_runbook,
    publish_revision,
    withdraw_revision,
)
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceDecision, IntelligenceDecisionCandidate, IntelligenceExecutionJournal
from app.models.knowledge import KnowledgeRunbook, KnowledgeRunbookRevision
from app.models.resolver import ResolverOperationalControl, ResolverProductionReadinessRecord
from app.notifications.service import queue_transient_feedback
from app.rbac.decorators import permission_required
from app.resolver.operations import requeue_dead_letter, update_control
from app.resolver.production_readiness import REQUIRED_CHECKS, advance_rollout_stage, record_validation

automation_control_bp = Blueprint(
    'automation_control',
    __name__,
    url_prefix='/intelligence',
)


@automation_control_bp.route('/automation-control')
@permission_required('intelligence.view')
def index() -> ResponseReturnValue:
    payload = build_automation_control_context(request.args)
    return render_template('intelligence/automation_control.html', payload=payload)


@automation_control_bp.post('/automation-control/runbooks')
@permission_required('knowledge.runbooks.manage')
def create_automation_runbook() -> ResponseReturnValue:
    return _handle_mutation(
        workspace='runbooks',
        success_title='Runbook created',
        success_message='KAORI created the stable runbook identity.',
        operation=lambda: create_runbook(
            runbook_key=request.form.get('runbook_key', ''),
            title=request.form.get('title', ''),
            description=_optional_text(request.form.get('description')),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.manage'),
        ),
    )


@automation_control_bp.post('/automation-control/revisions')
@automation_control_bp.post('/automation-control/runbooks/<int:runbook_id>/revisions')
@permission_required('knowledge.runbooks.manage')
def create_automation_revision(runbook_id: int | None = None) -> ResponseReturnValue:
    def operation() -> object:
        selected_runbook_id = runbook_id or _positive_int(request.form.get('runbook_id'), 'Runbook')
        runbook = db.session.get(KnowledgeRunbook, selected_runbook_id)
        if runbook is None:
            raise ValueError('Selected runbook no longer exists.')
        parameter_schema = _json_object(request.form.get('parameter_schema_json'), 'Parameter schema')
        steps = _json_list(request.form.get('steps_json'), 'Runbook steps')
        rollback = _optional_json_object(request.form.get('rollback_json'), 'Rollback definition')
        return create_revision(
            runbook,
            version=request.form.get('version', ''),
            action_key=request.form.get('action_key', ''),
            resolver_key=request.form.get('resolver_key', ''),
            approval_policy=request.form.get('approval_policy', 'needs_approval'),
            required_evidence=_csv(request.form.get('required_evidence')),
            required_capabilities=_csv(request.form.get('required_capabilities')),
            compatibility_profiles=_csv(request.form.get('compatibility_profiles')),
            change_level=request.form.get('change_level', 'patch'),
            parameter_schema=parameter_schema,
            steps=steps,
            rollback=rollback,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.manage'),
        )

    return _handle_mutation(
        workspace='runbooks',
        success_title='Runbook revision created',
        success_message='KAORI saved the immutable draft revision for review.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/revisions/<int:revision_id>/publish')
@permission_required('knowledge.runbooks.publish')
def publish_automation_revision(revision_id: int) -> ResponseReturnValue:
    def operation() -> object:
        revision = db.session.get(KnowledgeRunbookRevision, revision_id)
        if revision is None:
            raise ValueError('Selected runbook revision no longer exists.')
        registry = get_resolver_registry(current_app)
        descriptor = registry.describe(revision.action_key)
        compatibility_profile = _optional_text(request.form.get('compatibility_profile'))
        if compatibility_profile is None and len(descriptor.compatibility_profiles) == 1:
            compatibility_profile = descriptor.compatibility_profiles[0]
        return publish_revision(
            revision,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.publish'),
            resolver_registry=registry,
            available_capabilities=descriptor.capability_keys,
            compatibility_profile=compatibility_profile,
        )

    return _handle_mutation(
        workspace='runbooks',
        success_title='Runbook revision published',
        success_message='KAORI published the validated immutable runbook revision.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/revisions/<int:revision_id>/withdraw')
@permission_required('knowledge.runbooks.publish')
def withdraw_automation_revision(revision_id: int) -> ResponseReturnValue:
    def operation() -> object:
        revision = db.session.get(KnowledgeRunbookRevision, revision_id)
        if revision is None:
            raise ValueError('Selected runbook revision no longer exists.')
        return withdraw_revision(
            revision,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.publish'),
        )

    return _handle_mutation(
        workspace='runbooks',
        success_title='Runbook revision withdrawn',
        success_message='KAORI removed the revision from active alert matching.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/bindings')
@permission_required('knowledge.runbooks.manage')
def create_automation_binding() -> ResponseReturnValue:
    def operation() -> object:
        revision_id = _positive_int(request.form.get('revision_id'), 'Published revision')
        revision = db.session.get(KnowledgeRunbookRevision, revision_id)
        if revision is None:
            raise ValueError('Selected published revision no longer exists.')
        return create_alert_binding(
            revision,
            binding_key=request.form.get('binding_key', ''),
            rule_key=_optional_text(request.form.get('rule_key')),
            alertname=_optional_text(request.form.get('alertname')),
            cluster_id=_optional_text(request.form.get('cluster_id')),
            namespace=_optional_text(request.form.get('namespace')),
            required_labels=_json_object(request.form.get('required_labels_json'), 'Required labels'),
            evidence_mapping=_json_object(request.form.get('evidence_mapping_json'), 'Evidence mapping'),
            priority=_positive_int(request.form.get('priority', 100), 'Priority'),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.manage'),
        )

    return _handle_mutation(
        workspace='runbooks',
        success_title='Alert binding created',
        success_message='KAORI bound the alert selector to a published runbook revision.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/candidates/<int:candidate_id>/promote')
@permission_required('intelligence.decisions.create')
def promote_automation_candidate(candidate_id: int) -> ResponseReturnValue:
    def operation() -> object:
        candidate = db.session.get(IntelligenceDecisionCandidate, candidate_id)
        if candidate is None:
            raise ValueError('Selected decision candidate no longer exists.')
        global_control = ResolverOperationalControl.query.filter_by(cluster_id=None).one_or_none()
        cluster_control = ResolverOperationalControl.query.filter_by(cluster_id=candidate.cluster_id).one_or_none()
        maintenance_mode = bool(
            (global_control and global_control.global_kill_switch)
            or (cluster_control and cluster_control.maintenance_mode)
        )
        return promote_candidate(
            candidate,
            rule_version=request.form.get('rule_version', 'automation-control-v1'),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions(
                'intelligence.decisions.create',
                'intelligence.decisions.execute',
            ),
            reason=_optional_text(request.form.get('reason')),
            maintenance_mode=maintenance_mode,
            actor_can_execute=_actor_has_permission('intelligence.decisions.execute'),
        )

    return _handle_mutation(
        workspace='decisions',
        success_title='Candidate promoted',
        success_message='KAORI created an immutable decision snapshot from the reviewed candidate.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/candidates/<int:candidate_id>/dismiss')
@permission_required('intelligence.decisions.create')
def dismiss_automation_candidate(candidate_id: int) -> ResponseReturnValue:
    def operation() -> object:
        candidate = db.session.get(IntelligenceDecisionCandidate, candidate_id)
        if candidate is None:
            raise ValueError('Selected decision candidate no longer exists.')
        return dismiss_candidate(
            candidate,
            reason=request.form.get('reason', ''),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('intelligence.decisions.create'),
        )

    return _handle_mutation(
        workspace='decisions',
        success_title='Candidate dismissed',
        success_message='KAORI recorded the review outcome and retained the candidate evidence.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/decisions/<int:decision_id>/approve')
@permission_required('intelligence.decisions.approve')
def approve_automation_decision(decision_id: int) -> ResponseReturnValue:
    return _decision_outcome(decision_id, outcome='approved')


@automation_control_bp.post('/automation-control/decisions/<int:decision_id>/reject')
@permission_required('intelligence.decisions.approve')
def reject_automation_decision(decision_id: int) -> ResponseReturnValue:
    return _decision_outcome(decision_id, outcome='rejected')


@automation_control_bp.post('/automation-control/deployment-policies')
@permission_required('intelligence.decisions.execute')
def update_automation_deployment_policy() -> ResponseReturnValue:
    return _handle_mutation(
        workspace='operations',
        success_title='Deployment policy updated',
        success_message='KAORI updated the scoped resolver deployment policy.',
        operation=lambda: upsert_deployment_policy(
            cluster_id=request.form.get('cluster_id', ''),
            action_key=request.form.get('action_key', ''),
            lifecycle_status=request.form.get('lifecycle_status', 'disabled'),
            allowed_namespaces=_csv(request.form.get('allowed_namespaces')),
            required_registry_fingerprint=_optional_text(request.form.get('required_registry_fingerprint')),
            actor_user_id=_actor_user_id(),
        ),
    )


@automation_control_bp.post('/automation-control/operational-controls')
@permission_required('intelligence.decisions.execute')
def update_automation_operational_control() -> ResponseReturnValue:
    def operation() -> object:
        cluster_id = _optional_text(request.form.get('cluster_id'))
        record = update_control(
            cluster_id=cluster_id,
            global_kill_switch=('global_kill_switch' in request.form) if cluster_id is None else None,
            maintenance_mode='maintenance_mode' in request.form,
            concurrency_limit=_positive_int(request.form.get('concurrency_limit', 1), 'Concurrency limit'),
            rate_limit_per_minute=_positive_int(request.form.get('rate_limit_per_minute', 10), 'Rate limit'),
            circuit_failure_threshold=_positive_int(
                request.form.get('circuit_failure_threshold', 3), 'Circuit failure threshold'
            ),
            circuit_cooldown_seconds=_positive_int(
                request.form.get('circuit_cooldown_seconds', 300), 'Circuit cooldown'
            ),
            actor_user_id=_actor_user_id(),
        )
        db.session.commit()
        return record

    return _handle_mutation(
        workspace='operations',
        success_title='Operational control updated',
        success_message='KAORI applied the resolver safety posture to the selected scope.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/journals/<int:journal_id>/requeue')
@permission_required('intelligence.decisions.execute')
def requeue_automation_journal(journal_id: int) -> ResponseReturnValue:
    def operation() -> object:
        journal = db.session.get(IntelligenceExecutionJournal, journal_id)
        if journal is None:
            raise ValueError('Selected execution journal no longer exists.')
        requeue_dead_letter(journal, actor_user_id=_actor_user_id())
        db.session.commit()
        return journal

    return _handle_mutation(
        workspace='operations',
        success_title='Dead letter requeued',
        success_message='KAORI moved the execution journal back to retry wait.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/readiness')
@permission_required('intelligence.decisions.execute')
def record_automation_readiness() -> ResponseReturnValue:
    def operation() -> object:
        cluster_id = request.form.get('cluster_id', '').strip()
        action_key = request.form.get('action_key', '').strip()
        if db.session.get(Cluster, cluster_id) is None:
            raise ValueError('Selected cluster does not exist.')
        get_resolver_registry(current_app).describe(action_key)
        results = {check: check in request.form for check in REQUIRED_CHECKS}
        record = record_validation(
            cluster_id=cluster_id,
            action_key=action_key,
            results=results,
            actor_user_id=_actor_user_id(),
        )
        db.session.commit()
        return record

    return _handle_mutation(
        workspace='readiness',
        success_title='Readiness evidence recorded',
        success_message='KAORI stored the complete production-readiness evidence snapshot.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/readiness/<int:record_id>/stage')
@permission_required('intelligence.decisions.execute')
def advance_automation_readiness(record_id: int) -> ResponseReturnValue:
    def operation() -> object:
        record = db.session.get(ResolverProductionReadinessRecord, record_id)
        if record is None:
            raise ValueError('Selected readiness record no longer exists.')
        advance_rollout_stage(
            record,
            target_stage=request.form.get('target_stage', 'disabled'),
            actor_user_id=_actor_user_id(),
        )
        db.session.commit()
        return record

    return _handle_mutation(
        workspace='readiness',
        success_title='Rollout stage updated',
        success_message='KAORI advanced the resolver action through the controlled rollout sequence.',
        operation=operation,
    )


def _decision_outcome(decision_id: int, *, outcome: str) -> ResponseReturnValue:
    def operation() -> object:
        decision = db.session.get(IntelligenceDecision, decision_id)
        if decision is None:
            raise ValueError('Selected decision no longer exists.')
        reason = request.form.get('reason', '')
        if outcome == 'approved':
            return approve_decision(
                decision,
                actor_user_id=_actor_user_id(),
                actor_permissions=_actor_permissions('intelligence.decisions.approve'),
                reason=_optional_text(reason),
            )
        return reject_decision(
            decision,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('intelligence.decisions.approve'),
            reason=reason,
        )

    return _handle_mutation(
        workspace='decisions',
        success_title=f'Decision {outcome}',
        success_message=f'KAORI recorded the {outcome} authorization outcome.',
        operation=operation,
    )


def _handle_mutation(
    *,
    workspace: str,
    success_title: str,
    success_message: str,
    operation: Callable[[], object],
) -> ResponseReturnValue:
    if not current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False):
        queue_transient_feedback(
            status='warning',
            title='Automation Control Reserved Plan',
            message='KAORI did not apply the requested mutation.',
            detail='Mutation execution remains disabled until validation gates and behavioral tests are enabled.',
        )
        return redirect(url_for('automation_control.index', workspace=workspace))
    try:
        operation()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Automation Control mutation failed in workspace %s.', workspace)
        queue_transient_feedback(
            status='error',
            title='Automation Control update failed',
            message='KAORI did not apply the requested change.',
            detail='Review the application log and Activity Audit for the failure context before retrying.',
        )
    else:
        queue_transient_feedback(
            status='success',
            title=success_title,
            message=success_message,
        )
    return redirect(url_for('automation_control.index', workspace=workspace))


def _actor_user_id() -> int | None:
    value = getattr(current_user, 'id', None)
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _actor_has_permission(permission: str) -> bool:
    checker = getattr(current_user, 'has_permission', None)
    return bool(callable(checker) and checker(permission))


def _actor_permissions(*permissions: str) -> Collection[str]:
    return {permission for permission in permissions if _actor_has_permission(permission)}


def _optional_text(value: Any) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def _csv(value: Any) -> list[str]:
    return sorted({item.strip() for item in str(value or '').split(',') if item.strip()})


def _positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be a whole number.') from exc
    if parsed < 1:
        raise ValueError(f'{label} must be at least 1.')
    return parsed


def _json_object(value: Any, label: str) -> dict[str, Any]:
    normalized = str(value or '').strip() or '{}'
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{label} must contain valid JSON.') from exc
    if not isinstance(parsed, dict):
        raise ValueError(f'{label} must be a JSON object.')
    return parsed


def _optional_json_object(value: Any, label: str) -> dict[str, Any] | None:
    normalized = str(value or '').strip()
    return _json_object(normalized, label) if normalized else None


def _json_list(value: Any, label: str) -> list[dict[str, Any]]:
    normalized = str(value or '').strip() or '[]'
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{label} must contain valid JSON.') from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError(f'{label} must be a JSON array of objects.')
    return parsed
