from __future__ import annotations

import json
from collections.abc import Callable, Collection
from typing import Any, cast

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

from app.access.rbac.decorators import permission_required
from app.common.automation_execution import execution_enabled
from app.integrations.resolver_bootstrap import build_resolver_contract_registry, get_resolver_registry
from app.intelligence.automation_control.notifications import (
    APPROVAL_REQUIRED_EVENT,
    DECISION_APPROVED_EVENT,
    DECISION_REJECTED_EVENT,
)
from app.intelligence.automation_control.presentation import build_automation_control_context
from app.intelligence.automation_control.service import (
    commit_automation_control,
    get_cluster,
    get_decision,
    get_decision_candidate,
    get_readiness_record,
    get_runbook,
    get_runbook_binding,
    get_runbook_revision,
    rollback_automation_control,
    upsert_deployment_policy,
)
from app.intelligence.automation_control.tasks import dispatch_automation_decision_notification
from app.intelligence.knowledge.candidate_review import dismiss_candidate, promote_candidate
from app.intelligence.knowledge.matching import create_alert_binding, set_alert_binding_status
from app.intelligence.knowledge.service import (
    activate_system_runbook,
    assert_binding_uses_allowed_runbook,
    assert_custom_runbook_authoring_enabled,
    assert_revision_mutation_allowed,
    create_revision,
    create_runbook,
    publish_revision,
    withdraw_revision,
)
from app.intelligence.resolver.operations import assert_decision_execution_allowed, update_control
from app.intelligence.resolver.orchestration import enqueue_execution_delivery
from app.intelligence.resolver.production_readiness import (
    REQUIRED_CHECKS,
    advance_rollout_stage,
    assert_deployment_policy_allows,
    assert_production_execution_ready,
    record_validation,
)
from app.intelligence.resolver.tasks import execute_authorized_resolution
from app.intelligence.workflow import (
    approve_decision,
    issue_persisted_execution_token,
    reject_decision,
)
from app.platform_operations.notifications.service import record_operational_activity

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


@automation_control_bp.get('/automation-control/modals/binding')
@permission_required('knowledge.runbooks.manage')
def binding_configuration_modal() -> ResponseReturnValue:
    payload = build_automation_control_context({'workspace': 'runbooks'})
    return render_template(
        'intelligence/partials/automation_control/_binding_configuration_modal.html',
        payload=payload,
    )


@automation_control_bp.get('/automation-control/modals/execution-configuration')
@permission_required('intelligence.decisions.execute')
def execution_configuration_modal() -> ResponseReturnValue:
    payload = build_automation_control_context({'workspace': 'operations'})
    return render_template(
        'intelligence/partials/automation_control/_execution_configuration_modal.html',
        payload=payload,
    )


@automation_control_bp.get('/automation-control/modals/readiness')
@permission_required('intelligence.decisions.execute')
def readiness_configuration_modal() -> ResponseReturnValue:
    payload = build_automation_control_context({'workspace': 'readiness'})
    return render_template(
        'intelligence/partials/automation_control/_readiness_configuration_modal.html',
        payload=payload,
    )


@automation_control_bp.post('/automation-control/system-runbooks/<string:runbook_key>/activate')
@permission_required('knowledge.runbooks.publish')
def activate_automation_system_runbook(runbook_key: str) -> ResponseReturnValue:
    return _handle_governance_mutation(
        workspace='runbooks',
        success_title='System Runbook activated',
        success_message='KAORI activated the validated source-controlled runbook revision for binding.',
        operation=lambda: activate_system_runbook(
            runbook_key=runbook_key,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.manage', 'knowledge.runbooks.publish'),
            resolver_registry=build_resolver_contract_registry(),
        ),
    )


@automation_control_bp.post('/automation-control/runbooks')
@permission_required('knowledge.runbooks.manage')
def create_automation_runbook() -> ResponseReturnValue:
    def operation() -> object:
        assert_custom_runbook_authoring_enabled(current_app.config)
        return create_runbook(
            runbook_key=request.form.get('runbook_key', ''),
            title=request.form.get('title', ''),
            description=_optional_text(request.form.get('description')),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.manage'),
        )

    return _handle_governance_mutation(
        workspace='runbooks',
        success_title='Runbook created',
        success_message='KAORI created the custom runbook identity.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/revisions')
@automation_control_bp.post('/automation-control/runbooks/<int:runbook_id>/revisions')
@permission_required('knowledge.runbooks.manage')
def create_automation_revision(runbook_id: int | None = None) -> ResponseReturnValue:
    def operation() -> object:
        assert_custom_runbook_authoring_enabled(current_app.config)
        selected_runbook_id = runbook_id or _positive_int(request.form.get('runbook_id'), 'Runbook')
        runbook = get_runbook(selected_runbook_id)
        if runbook is None:
            raise ValueError('Selected runbook no longer exists.')
        parameter_schema = _json_object(request.form.get('parameter_schema_json'), 'Parameter schema')
        steps = _json_list(request.form.get('steps_json'), 'Runbook steps')
        rollback = _optional_json_object(request.form.get('rollback_json'), 'Recovery / rollback definition')
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

    return _handle_governance_mutation(
        workspace='runbooks',
        success_title='Runbook revision created',
        success_message='KAORI saved the immutable draft revision for review.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/revisions/<int:revision_id>/publish')
@permission_required('knowledge.runbooks.publish')
def publish_automation_revision(revision_id: int) -> ResponseReturnValue:
    def operation() -> object:
        revision = get_runbook_revision(revision_id)
        if revision is None:
            raise ValueError('Selected runbook revision no longer exists.')
        assert_revision_mutation_allowed(revision, config=current_app.config, operation='published')
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

    return _handle_governance_mutation(
        workspace='runbooks',
        success_title='Runbook revision published',
        success_message='KAORI published the validated immutable runbook revision.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/revisions/<int:revision_id>/withdraw')
@permission_required('knowledge.runbooks.publish')
def withdraw_automation_revision(revision_id: int) -> ResponseReturnValue:
    def operation() -> object:
        revision = get_runbook_revision(revision_id)
        if revision is None:
            raise ValueError('Selected runbook revision no longer exists.')
        assert_revision_mutation_allowed(revision, config=current_app.config, operation='withdrawn')
        return withdraw_revision(
            revision,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.publish'),
        )

    return _handle_governance_mutation(
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
        revision = get_runbook_revision(revision_id)
        if revision is None:
            raise ValueError('Selected published revision no longer exists.')
        assert_binding_uses_allowed_runbook(revision, config=current_app.config)
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

    return _handle_governance_mutation(
        workspace='runbooks',
        success_title='Alert binding created',
        success_message='KAORI bound the alert selector to a published runbook revision.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/bindings/<int:binding_id>/status')
@permission_required('knowledge.runbooks.manage')
def update_automation_binding_status(binding_id: int) -> ResponseReturnValue:
    def operation() -> object:
        binding = get_runbook_binding(binding_id)
        if binding is None:
            raise ValueError('Selected runbook binding no longer exists.')
        return set_alert_binding_status(
            binding,
            lifecycle_status=request.form.get('lifecycle_status', ''),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('knowledge.runbooks.manage'),
        )

    return _handle_governance_mutation(
        workspace='runbooks',
        success_title='Binding status updated',
        success_message='KAORI updated candidate matching availability for the selected binding.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/candidates/<int:candidate_id>/promote')
@permission_required('intelligence.decisions.create')
def promote_automation_candidate(candidate_id: int) -> ResponseReturnValue:
    def operation() -> object:
        candidate = get_decision_candidate(candidate_id)
        if candidate is None:
            raise ValueError('Selected decision candidate no longer exists.')
        decision = promote_candidate(
            candidate,
            rule_version=request.form.get('rule_version', 'automation-control-v1'),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('intelligence.decisions.create'),
            reason=_optional_text(request.form.get('reason')),
        )
        if decision.workflow_status == 'pending_approval':
            _queue_decision_notification(decision.id, APPROVAL_REQUIRED_EVENT)
        return decision

    return _handle_governance_action(
        workspace='decisions',
        success_title='Candidate promoted',
        success_message='KAORI created an immutable decision snapshot from the reviewed candidate.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/candidates/<int:candidate_id>/dismiss')
@permission_required('intelligence.decisions.create')
def dismiss_automation_candidate(candidate_id: int) -> ResponseReturnValue:
    def operation() -> object:
        candidate = get_decision_candidate(candidate_id)
        if candidate is None:
            raise ValueError('Selected decision candidate no longer exists.')
        return dismiss_candidate(
            candidate,
            reason=request.form.get('reason', ''),
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('intelligence.decisions.create'),
        )

    return _handle_governance_action(
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


@automation_control_bp.post('/automation-control/decisions/<int:decision_id>/execute')
@permission_required('intelligence.decisions.execute')
def execute_automation_decision(decision_id: int) -> ResponseReturnValue:
    def operation() -> object:
        decision = get_decision(decision_id)
        if decision is None:
            raise ValueError('Selected decision no longer exists.')
        cluster_id = str(decision.cluster_id or '').strip()
        if not cluster_id:
            raise ValueError('Resolver execution requires a cluster-scoped decision.')
        cluster = get_cluster(cluster_id)
        if cluster is None:
            raise ValueError('Resolver target cluster does not exist.')
        registry = get_resolver_registry(current_app)
        registry.describe(decision.action_key)
        assert_deployment_policy_allows(
            cluster_id=cluster_id,
            namespace=decision.namespace,
            action_key=decision.action_key,
            registry_fingerprint=str(current_app.config.get('RESOLVER_REGISTRY_FINGERPRINT') or ''),
        )
        assert_production_execution_ready(
            cluster_id=cluster_id,
            action_key=decision.action_key,
            cluster_environment=cluster.environment,
        )
        assert_decision_execution_allowed(decision)
        signing_key = str(current_app.config.get('RESOLVER_TOKEN_SIGNING_KEY') or '')
        token, journal = issue_persisted_execution_token(
            decision,
            secret_key=signing_key,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('intelligence.decisions.execute'),
        )
        enqueue_execution_delivery(
            journal,
            task=execute_authorized_resolution,
            token=token,
            actor_user_id=_actor_user_id(),
        )
        return journal

    return _handle_execution_action(
        workspace='operations',
        success_title='Execution queued',
        success_message='KAORI authorized the immutable decision and queued the canonical resolver job.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/deployment-policies')
@permission_required('intelligence.decisions.execute')
def update_automation_deployment_policy() -> ResponseReturnValue:
    return _handle_governance_mutation(
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
        commit_automation_control()
        return record

    return _handle_governance_mutation(
        workspace='operations',
        success_title='Operational control updated',
        success_message='KAORI applied the resolver safety posture to the selected scope.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/readiness')
@permission_required('intelligence.decisions.execute')
def record_automation_readiness() -> ResponseReturnValue:
    def operation() -> object:
        cluster_id = request.form.get('cluster_id', '').strip()
        action_key = request.form.get('action_key', '').strip()
        if get_cluster(cluster_id) is None:
            raise ValueError('Selected cluster does not exist.')
        get_resolver_registry(current_app).describe(action_key)
        results = {check: check in request.form for check in REQUIRED_CHECKS}
        record = record_validation(
            cluster_id=cluster_id,
            action_key=action_key,
            results=results,
            actor_user_id=_actor_user_id(),
        )
        commit_automation_control()
        return record

    return _handle_governance_mutation(
        workspace='readiness',
        success_title='Readiness evidence recorded',
        success_message='KAORI stored the complete production-readiness evidence snapshot.',
        operation=operation,
    )


@automation_control_bp.post('/automation-control/readiness/<int:record_id>/stage')
@permission_required('intelligence.decisions.execute')
def advance_automation_readiness(record_id: int) -> ResponseReturnValue:
    def operation() -> object:
        record = get_readiness_record(record_id)
        if record is None:
            raise ValueError('Selected readiness record no longer exists.')
        advance_rollout_stage(
            record,
            target_stage=request.form.get('target_stage', 'disabled'),
            actor_user_id=_actor_user_id(),
        )
        commit_automation_control()
        return record

    return _handle_governance_mutation(
        workspace='readiness',
        success_title='Rollout stage updated',
        success_message='KAORI advanced the resolver action through the controlled rollout sequence.',
        operation=operation,
    )


def _decision_outcome(decision_id: int, *, outcome: str) -> ResponseReturnValue:
    def operation() -> object:
        decision = get_decision(decision_id)
        if decision is None:
            raise ValueError('Selected decision no longer exists.')
        reason = request.form.get('reason', '')
        if outcome == 'approved':
            approve_decision(
                decision,
                actor_user_id=_actor_user_id(),
                actor_permissions=_actor_permissions('intelligence.decisions.approve'),
                reason=_optional_text(reason),
            )
            _queue_decision_notification(decision.id, DECISION_APPROVED_EVENT)
            return decision
        reject_decision(
            decision,
            actor_user_id=_actor_user_id(),
            actor_permissions=_actor_permissions('intelligence.decisions.approve'),
            reason=reason,
        )
        _queue_decision_notification(decision.id, DECISION_REJECTED_EVENT)
        return decision

    return _handle_governance_action(
        workspace='decisions',
        success_title=f'Decision {outcome}',
        success_message=f'KAORI recorded the {outcome} authorization outcome.',
        operation=operation,
    )


def _handle_governance_action(
    *,
    workspace: str,
    success_title: str,
    success_message: str,
    operation: Callable[[], object],
) -> ResponseReturnValue:
    """Persist accountable decision governance while infrastructure mutation remains independently gated."""
    return _handle_control_operation(
        workspace=workspace,
        success_title=success_title,
        success_message=success_message,
        failure_title='Automation governance update failed',
        failure_message='KAORI did not record the requested governance outcome.',
        operation=operation,
    )


def _handle_governance_mutation(
    *,
    workspace: str,
    success_title: str,
    success_message: str,
    operation: Callable[[], object],
) -> ResponseReturnValue:
    """Persist control-plane governance without crossing the infrastructure execution boundary."""
    return _handle_control_operation(
        workspace=workspace,
        success_title=success_title,
        success_message=success_message,
        failure_title='Automation Control update failed',
        failure_message='KAORI did not apply the requested governance configuration.',
        operation=operation,
    )


def _handle_execution_action(
    *,
    workspace: str,
    success_title: str,
    success_message: str,
    operation: Callable[[], object],
) -> ResponseReturnValue:
    if not execution_enabled():
        record_operational_activity(
            user_id=_actor_user_id(),
            event_type='automation_control_execution_blocked',
            status='warning',
            title='Infrastructure Execution Disabled',
            message='KAORI did not cross the resolver execution boundary.',
            detail=(
                'Governance configuration remains available. Set AUTOMATION_EXECUTION_ENABLED only after '
                'the production-readiness blockers are clear.'
            ),
            action_url=url_for('automation_control.index', workspace=workspace),
            metadata={'module': 'Intelligence', 'workspace': workspace},
            queue_feedback=True,
            delivery_policy='deck_on_failure',
        )
        return redirect(url_for('automation_control.index', workspace=workspace))
    return _handle_control_operation(
        workspace=workspace,
        success_title=success_title,
        success_message=success_message,
        failure_title='Automation execution failed',
        failure_message='KAORI did not queue the requested resolver execution.',
        operation=operation,
    )


def _handle_control_operation(
    *,
    workspace: str,
    success_title: str,
    success_message: str,
    failure_title: str,
    failure_message: str,
    operation: Callable[[], object],
) -> ResponseReturnValue:
    try:
        operation()
    except Exception:
        rollback_automation_control()
        current_app.logger.exception('Automation Control operation failed in workspace %s.', workspace)
        record_operational_activity(
            user_id=_actor_user_id(),
            event_type=f'automation_control_{workspace}_update_failed',
            status='error',
            title=failure_title,
            message=failure_message,
            detail='Review the application log and Activity Audit for the failure context before retrying.',
            action_url=url_for('automation_control.index', workspace=workspace),
            metadata={'module': 'Intelligence', 'workspace': workspace},
            queue_feedback=True,
            delivery_policy='deck_on_failure',
        )
    else:
        record_operational_activity(
            user_id=_actor_user_id(),
            event_type=f'automation_control_{workspace}_updated',
            status='success',
            title=success_title,
            message=success_message,
            action_url=url_for('automation_control.index', workspace=workspace),
            metadata={'module': 'Intelligence', 'workspace': workspace},
            queue_feedback=True,
            delivery_policy='audit_only',
        )
    return redirect(url_for('automation_control.index', workspace=workspace))


def _queue_decision_notification(decision_id: int, event_type: str) -> bool:
    try:
        cast(Any, dispatch_automation_decision_notification).delay(decision_id, event_type)
    except (RuntimeError, ConnectionError, OSError):
        current_app.logger.exception(
            'Automation Control could not enqueue notification event %s for decision %s.',
            event_type,
            decision_id,
        )
        return False
    return True


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
