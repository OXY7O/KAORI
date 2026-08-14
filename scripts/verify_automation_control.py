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
    routes = read('app/automation_control/routes.py')
    presentation = read('app/automation_control/presentation.py')
    overview_logic = read('app/automation_control/overview.py')
    main_template = read('app/templates/intelligence/automation_control.html')
    overview = read('app/templates/intelligence/partials/automation_control/_overview.html')
    runbooks = read('app/templates/intelligence/partials/automation_control/_runbooks.html')
    decisions = read('app/templates/intelligence/partials/automation_control/_decisions.html')
    operations = read('app/templates/intelligence/partials/automation_control/_operations.html')
    readiness = read('app/templates/intelligence/partials/automation_control/_readiness.html')
    notification_forms = read('app/notification_channels/forms.py')
    notification_service = read('app/notification_channels/service.py')
    default_config = read('app/config/default.py')
    env_example = read('.env.example')
    env_production = read('.env.production.example')

    for required in (
        "@automation_control_bp.route('/automation-control')",
        "current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)",
        "title='Automation Mutation Disabled'",
        'Governance Only',
    ):
        source = routes if required != 'Governance Only' else main_template
        require(required in source, f'Automation Control fail-closed contract missing: {required}', errors)

    gate = routes.split('def _handle_mutation(', 1)[1].split('def _actor_user_id(', 1)[0]
    require(gate.index("current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)") < gate.index('operation()'), 'Automation mutation callback can run before the global gate', errors)
    require('detail=str(exc)' not in routes, 'Automation Control must not expose raw exception detail', errors)
    require('AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in default_config, 'Automation mutation enablement must not be promoted into default config yet', errors)
    require('AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in env_example, 'Automation mutation enablement must not be exposed in development env template yet', errors)
    require('AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in env_production, 'Automation mutation enablement must not be exposed in production env template yet', errors)

    require('DOMAIN_DEFINITIONS' not in presentation, 'Legacy Domain 1–20 Foundation Map ownership must be removed from Automation Control presentation', errors)
    require('build_automation_overview' in presentation, 'Automation Overview must use the canonical posture builder', errors)
    for required in (
        'Decision & Execution Pipeline',
        'Automation Guardrails',
        'Recent Decision Activity',
        'Execution Activity',
    ):
        require(required in overview, f'Automation Overview workspace missing: {required}', errors)
    require('Foundation Map' not in overview, 'Automation Overview must not regress to the implementation-foundation map', errors)

    require("('overview', 'Overview', 'layout-dashboard')" in presentation, 'Automation workspace tab must use Overview label', errors)
    require("('operations', 'Execution Control', 'server-cog')" in presentation, 'Resolver Operations must be presented as Execution Control', errors)

    for required in (
        'Runbook & Binding Posture',
        'Revision Execution Eligibility',
        'Alert & Rule Bindings',
        'Advisory Only',
        'Approval Required',
        'Policy Eligible',
    ):
        source = runbooks if required not in {'Advisory Only', 'Approval Required', 'Policy Eligible'} else presentation
        require(required in source, f'Runbook governance contract missing: {required}', errors)

    require('Execution Journal' not in decisions, 'Execution journals must not be owned by Decision Review', errors)
    for required in ('Decision Contract', 'Candidate Review Queue', 'Persisted Decisions', 'Decision Mutations Disabled'):
        require(required in decisions, f'Decision Review contract missing: {required}', errors)

    for required in (
        'Execution Posture',
        'Resolver Registry',
        'Safety Controls',
        'Deployment Policies',
        'Execution Journal',
        'Dead-Letter Review',
        'Infrastructure Mutation Boundary',
    ):
        require(required in operations, f'Execution Control contract missing: {required}', errors)

    for required in (
        'Production Enablement Gate',
        'Controlled Rollout Sequence',
        'Readiness Evidence Contract',
        'Readiness Records',
    ):
        require(required in readiness, f'Production Readiness contract missing: {required}', errors)

    for forbidden in ('reserved_plan(', 'Reserved Plan'):
        automation_templates = '\n'.join((overview, runbooks, decisions, operations, readiness, main_template))
        require(forbidden not in automation_templates, f'Automation Control must use factual current-state wording instead of {forbidden}', errors)

    for event_type in (
        'automation.approval_required',
        'automation.execution_started',
        'automation.execution_completed',
        'automation.execution_failed',
        'automation.verification_failed',
    ):
        require(event_type in notification_forms, f'Notification Channel allowed-use contract missing {event_type}', errors)
        require(event_type in notification_service, f'Notification Channel label contract missing {event_type}', errors)
        require(event_type in overview_logic, f'Automation notification-readiness contract missing {event_type}', errors)

    require("action_key = 'kubernetes.deployment.restart'" in overview_logic, 'Controlled execution pilot must remain the allowlisted Kubernetes Deployment restart action', errors)
    require('Contract Required' in overview_logic, 'Verification must remain a distinct required contract', errors)

    if errors:
        print('FAIL — KAORI Automation Control')
        for error in errors:
            print(f'- {error}')
        return 1
    print('PASS — KAORI Automation Control')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
