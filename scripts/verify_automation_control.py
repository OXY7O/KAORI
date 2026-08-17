#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    routes = read('app/intelligence/automation_control/routes.py')
    presentation = read('app/intelligence/automation_control/presentation.py')
    overview_logic = read('app/intelligence/automation_control/overview.py')
    candidates = read('app/intelligence/automation_control/candidates.py')
    automation_tasks = read('app/intelligence/automation_control/tasks.py')
    workflow = read('app/intelligence/workflow.py')
    resolver_tasks = read('app/intelligence/resolver/tasks.py')
    resolver_service = read('app/intelligence/resolver/service.py')
    resolver_operations = read('app/intelligence/resolver/operations.py')
    resolver_orchestration = read('app/intelligence/resolver/orchestration.py')
    resolver_registry = read('app/intelligence/resolver/registry.py')
    resolver_adapter = read(
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/resolver_adapter.py'
    )
    config = read('app/config/default.py')
    env_example = read('.env.example')
    env_production = read('.env.production.example')
    main_template = read('app/templates/intelligence/automation_control.html')
    overview = read('app/templates/intelligence/partials/automation_control/_overview.html')
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    notification_forms = read('app/integrations/delivery/notification_channels/forms.py')
    notification_service = read('app/integrations/delivery/notification_channels/service.py')
    decision_notifications = read('app/intelligence/automation_control/notifications.py')
    execution_notifications = read('app/intelligence/resolver/notifications.py')
    system_runbook_catalog = read('app/intelligence/knowledge/system_catalog.py')
    knowledge_service = read('app/intelligence/knowledge/service.py')
    knowledge_matching = read('app/intelligence/knowledge/matching.py')
    resolver_bootstrap = read('app/integrations/resolver_bootstrap.py')

    # Default-deny execution boundary is explicit and independent from governance writes.
    for source in (config, env_example, env_production):
        require(
            'AUTOMATION_EXECUTION_ENABLED' in source, 'Execution enablement must be explicitly configurable', errors
        )
        require('CUSTOM_RUNBOOK_AUTHORING_ENABLED' in source, 'Custom runbook authoring lock must be explicit', errors)
    require(
        "AUTOMATION_EXECUTION_ENABLED = _env_bool('AUTOMATION_EXECUTION_ENABLED', False)" in config,
        'Execution must default false',
        errors,
    )
    require(
        "CUSTOM_RUNBOOK_AUTHORING_ENABLED = _env_bool('CUSTOM_RUNBOOK_AUTHORING_ENABLED', False)" in config,
        'Custom runbook authoring must default false',
        errors,
    )
    combined = '\n'.join((routes, presentation, config, env_example, env_production))
    require('AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in combined, 'Legacy all-mutations gate must not return', errors)
    require('def _handle_governance_mutation(' in routes, 'Governance write boundary is missing', errors)
    require(
        'def _handle_execution_action(' in routes and 'execution_enabled()' in routes,
        'Execution route gate is missing',
        errors,
    )
    require('assert_execution_enabled()' in workflow, 'Execution authorization must enforce the hard gate', errors)
    require('assert_execution_enabled()' in resolver_tasks, 'Resolver worker must enforce the hard gate again', errors)
    require('detail=str(exc)' not in routes, 'Automation Control must not expose raw exception detail', errors)

    # Evidence -> candidate -> decision -> approval -> authorization -> canonical job.
    require(
        'match_alert_to_runbook' in candidates and 'persist_candidate' in candidates,
        'Candidate producer must connect normalized alert evidence to persisted candidates',
        errors,
    )
    require(
        'materialize_active_alert_candidates' in automation_tasks, 'Candidate materialization task is missing', errors
    )
    require('automation-candidate-materialization' in config, 'Candidate materializer must be scheduled', errors)
    require(
        'minimum_outcome=PolicyOutcome(revision.approval_policy)'
        in read('app/intelligence/knowledge/candidate_review.py'),
        'Promotion policy must derive from immutable runbook policy',
        errors,
    )
    require(
        'actor_can_execute' not in read('app/intelligence/knowledge/candidate_review.py'),
        'Reviewer execute permission must not determine decision policy',
        errors,
    )
    require(
        'maker-checker separation' in workflow,
        'Approval-required decisions must enforce maker-checker separation',
        errors,
    )
    require(
        "'/automation-control/decisions/<int:decision_id>/execute'" in routes,
        'Approved decision execution handoff route is missing',
        errors,
    )
    require(
        'issue_persisted_execution_token' in routes and 'enqueue_execution_delivery' in routes,
        'Execution handoff must issue one-time authorization and canonical job',
        errors,
    )
    require(
        'build_idempotency_key' in workflow and 'already has an execution authorization' in workflow,
        'One immutable decision must not issue duplicate execution authorizations',
        errors,
    )

    # Admission: application preflight + worker revalidation + operational controls.
    require(
        'assert_deployment_policy_allows' in routes and 'assert_production_execution_ready' in routes,
        'Application execution eligibility preflight is incomplete',
        errors,
    )
    require(
        'assert_decision_execution_allowed(decision)' in routes,
        'Application safety-control preflight is missing',
        errors,
    )
    require(
        'assert_deployment_policy_allows' in resolver_tasks and 'assert_production_execution_ready' in resolver_tasks,
        'Worker production admission must be authoritative',
        errors,
    )
    require('global_control.maintenance_mode' in resolver_operations, 'Global maintenance must block execution', errors)
    require(
        'worker_lost_after_token_consumed' in resolver_orchestration,
        'Worker loss after token consumption must never replay mutation',
        errors,
    )
    require(
        "journal.status = 'canceled'" in resolver_orchestration
        and "journal.orchestration_status = 'dead_letter'" in resolver_orchestration,
        'Failed or expired one-time authorization must terminalize safely',
        errors,
    )
    require(
        'requeue_dead_letter' not in routes,
        'Consumed one-time execution journals must not expose unsafe manual replay',
        errors,
    )

    # Dry-run, execution, post-action verification and recovery semantics.
    require("'dry_run':" in resolver_service, 'Server-side dry-run evidence must be persisted', errors)
    require('def verify_resolver_execution(' in resolver_service, 'Post-action verification service is missing', errors)
    require(
        "name='app.intelligence.resolver.tasks.verify_authorized_resolution'" in resolver_tasks,
        'Post-action verification task is missing',
        errors,
    )
    require(
        'def verify(' in resolver_adapter and 'ProgressDeadlineExceeded' in resolver_adapter,
        'Kubernetes adapter must verify rollout health',
        errors,
    )
    require(
        'manual_compensating_recovery' in resolver_adapter,
        'Non-reversible restart must record compensating-recovery evidence',
        errors,
    )
    require(
        'rollback_required = False' in resolver_adapter, 'Deployment restart must not claim automatic rollback', errors
    )
    require(
        'post-action verification' in resolver_registry.lower(),
        'Resolver registry must require verification-capable adapters',
        errors,
    )

    # TTL reconciliation and lifecycle notification producers.
    require(
        'expire_stale_candidates' in automation_tasks and 'expire_stale_decisions' in automation_tasks,
        'Candidate/decision TTL reconciler is incomplete',
        errors,
    )
    require(
        'expire_stale_execution_authorizations' in automation_tasks,
        'Unused execution authorization TTL reconciliation is missing',
        errors,
    )
    require('automation-lifecycle-reconciliation' in config, 'Lifecycle reconciler must be scheduled', errors)
    events = (
        'automation.approval_required',
        'automation.decision_approved',
        'automation.decision_rejected',
        'automation.execution_started',
        'automation.execution_completed',
        'automation.execution_failed',
        'automation.verification_failed',
    )
    for event_type in events:
        require(event_type in notification_forms, f'Notification Channel contract missing {event_type}', errors)
        require(event_type in notification_service, f'Notification label contract missing {event_type}', errors)
        require(
            event_type in decision_notifications + execution_notifications,
            f'Automation lifecycle producer contract missing {event_type}',
            errors,
        )
    require(
        'dispatch_resolver_execution_notification' in resolver_tasks,
        'Execution lifecycle notification task is missing',
        errors,
    )

    # KAORI operational UI owns every transition; no hidden endpoint-only governance.
    require(
        'Governance Only' in main_template and 'Execution Disabled' in main_template,
        'Default UI posture must be factual',
        errors,
    )
    for required in ('Control Path', 'Safety & Readiness', 'Current Activity'):
        require(required in overview, f'Overview contract missing: {required}', errors)
    for required in (
        'System Runbook Catalog',
        'Activate System Runbook',
        'Binding Configuration',
        'Create Binding',
        'Custom Authoring Locked',
    ):
        require(required in runbooks, f'System Runbook Catalog UI missing: {required}', errors)
    for forbidden in ('Create Runbook', 'Create Revision', 'Publish Revision'):
        require(
            forbidden not in runbooks,
            f'Manual runbook authoring must not be exposed in the supported UI: {forbidden}',
            errors,
        )
    require(
        'kubernetes.deployment.restart' in system_runbook_catalog,
        'Validated Deployment restart System Runbook is missing',
        errors,
    )
    require(
        "validation_status='system_tested'" in system_runbook_catalog,
        'System Runbook must declare tested catalog posture',
        errors,
    )
    require(
        'post-action rollout verification' in system_runbook_catalog.lower(),
        'System Runbook must document verification contract',
        errors,
    )
    require(
        'manual_compensating_recovery' in system_runbook_catalog,
        'System Runbook must preserve recovery semantics',
        errors,
    )
    require(
        'activate_system_runbook' in routes and 'activate_system_runbook' in knowledge_service,
        'System Runbook activation flow is missing',
        errors,
    )
    require(
        'build_resolver_contract_registry' in routes and 'build_resolver_contract_registry' in resolver_bootstrap,
        'System Runbook activation must validate against a build contract registry independent from execution registration',
        errors,
    )
    require(
        'CATALOG_VALIDATION_NAMESPACE' in resolver_bootstrap,
        'Resolver contract registry must remain validation-only and fail-closed for execution use',
        errors,
    )
    require(
        'catalog drift detected' in knowledge_service.lower(),
        'System Runbook activation must fail closed on immutable catalog drift',
        errors,
    )
    require(
        'assert_custom_runbook_authoring_enabled' in routes,
        'Legacy custom authoring endpoints must remain guarded',
        errors,
    )
    require(
        'assert_binding_uses_allowed_runbook' in routes,
        'Bindings must reject custom runbooks while custom authoring is locked',
        errors,
    )
    require(
        'update_automation_binding_status' in routes and 'set_alert_binding_status' in knowledge_matching,
        'Binding lifecycle must support governed enable/disable without deletion',
        errors,
    )
    require(
        'Disable Binding' in runbooks and 'Enable Binding' in runbooks,
        'Binding lifecycle controls are missing from the Runbook workspace',
        errors,
    )
    for required in ('Candidate Review Queue', 'Persisted Decisions', 'Maker-Checker', 'Queue Execution'):
        require(required in decisions, f'Decision workflow UI missing: {required}', errors)
    for required in (
        'Governance Configuration',
        'Deployment Policies',
        'Safety Controls',
        'Execution Journal',
        'Post-action Verification',
        'Dead-Letter Review',
    ):
        require(required in operations, f'Execution Control UI missing: {required}', errors)
    for required in (
        'Production Enablement Gate',
        'Readiness Configuration',
        'Record Evidence',
        'Controlled Rollout Sequence',
        'Apply Stage',
    ):
        require(required in readiness, f'Production Readiness UI missing: {required}', errors)

    require(
        "action_key = 'kubernetes.deployment.restart'" in overview_logic,
        'First controlled execution pilot must remain Kubernetes Deployment restart',
        errors,
    )
    require('DOMAIN_DEFINITIONS' not in presentation, 'Legacy foundation-map ownership must not return', errors)

    if errors:
        print('FAIL — KAORI Automation Control')
        for error in errors:
            print(f'- {error}')
        return 1
    print('PASS — KAORI Automation Control · end-to-end governed lifecycle')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
