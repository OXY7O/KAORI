# Automation Control Center UI

## Purpose

Automation Control is KAORI's governed bridge from Intelligence evidence to future controlled execution. It does not own rule evaluation, Alertmanager routing, Kubernetes inventory, or provider-specific mutation logic. It coordinates their public contracts into an operator-facing decision, execution-safety, and readiness workspace.

Route: `GET /intelligence/automation-control`

Navigation: **Intelligence → Automation Control**

Ownership boundary: `app/automation_control/` remains an application orchestration layer. Knowledge, Intelligence, Resolver, Notification Channels, and Integration domains do not import it. Automation Control may consume their public read/service contracts without creating reverse dependencies.

## Workspace structure

| Workspace | Operator question | Current capability |
|---|---|---|
| Overview | What is the automation control posture right now? | Decision pipeline, pending work, execution activity, mutation state, safety controls, production readiness, notification delivery, and the controlled pilot boundary. |
| Runbooks & Bindings | Which evidence can map to which governed procedure? | Stable runbooks, immutable revisions, approval policy, rollback evidence, resolver action identity, and deterministic alert/rule bindings. |
| Decision Review | What is awaiting accountable review? | Non-executable candidates, immutable decisions, policy outcome, approval requirement, evidence hash, scope, and expiry. |
| Execution Control | What can execute and what is happening now? | Resolver registry, deployment policies, safety controls, execution journals, retry state, and dead letters. |
| Production Readiness | What still blocks controlled execution? | Mutation gate, registry coverage, deployment policy, readiness evidence, Notification Channel coverage, and ordered rollout stage. |

The old Domain 1–20 Foundation Map is no longer an operator surface. Architecture implementation history remains documented elsewhere; Automation Overview now reports operational control state.

## Current mutation boundary

`AUTOMATION_CONTROL_MUTATIONS_ENABLED` resolves false when absent and is deliberately not exposed through `.env.example` or `.env.production.example` during the current baseline lock.

When disabled:

- read/evidence workspaces remain available;
- direct POST requests fail closed before invoking the operation callback;
- feedback is **Automation Mutation Disabled**;
- the page posture is **Governance Only**;
- runbook, decision, deployment-policy, safety-control, dead-letter, readiness-stage, and infrastructure mutations are not applied.

This state is not labelled `Reserved Plan`: the control/evidence capability exists; only state-changing control-plane behavior is intentionally disabled.

## Governed lifecycle

```text
Evidence
   ↓
Runbook Match
   ↓
Decision Candidate
   ↓
Decision & Approval
   ↓
Controlled Execution
   ↓
Post-action Verification
```

A candidate is never executable. A persisted decision remains separate from an execution journal. Resolver/API success remains separate from remediation verification.

## Resolver execution boundary

Only typed, registered actions may cross the resolver boundary. Arbitrary shell commands or free-form `kubectl` execution are not part of the automation contract.

The intended first controlled execution pilot remains:

```text
kubernetes.deployment.restart
```

Registration alone does not make the action executable. The pilot requires:

1. immutable runbook revision and deterministic binding;
2. explicit decision policy and approval when required;
3. active cluster/namespace deployment policy;
4. current resolver-registry fingerprint;
5. server-side dry-run evidence;
6. rollback definition;
7. global/cluster safety-control admission;
8. complete production-readiness checks;
9. execution journal and Activity Audit evidence;
10. Notification Channel coverage for automation lifecycle events; and
11. post-action verification before remediation is considered successful.

## Notification delivery

Notification Channels remains Integrations-owned. Automation Control only declares delivery-event contracts:

- `automation.approval_required`
- `automation.execution_started`
- `automation.execution_completed`
- `automation.execution_failed`
- `automation.verification_failed`

Configured Telegram, Email, or Microsoft Teams channels may opt into those uses. No provider credential or transport code belongs in Automation Control.

## Production-readiness semantics

Readiness is not one boolean. The UI reports these independently:

- Mutation Gate
- Resolver Registry
- Active Deployment Policies
- Readiness Evidence
- Notification Delivery
- Global Kill Switch
- Maintenance Mode

Rollout remains ordered:

```text
Disabled → Shadow → Non-Production → Canary → Production
```

Stage skipping remains prohibited.

## Permission boundaries

| Capability | Required permission |
|---|---|
| View workspace | `intelligence.view` |
| Create runbook/revision/binding | `knowledge.runbooks.manage` |
| Publish or withdraw revision | `knowledge.runbooks.publish` |
| Promote or dismiss candidate | `intelligence.decisions.create` |
| Approve or reject decision | `intelligence.decisions.approve` |
| Manage policy/control/readiness/dead letters | `intelligence.decisions.execute` |

Permissions do not bypass the global mutation gate.

## Quality contract

`scripts/verify_automation_control.py` locks:

- default fail-closed mutation behavior;
- no environment-configured mutation enablement;
- operational Overview ownership rather than Foundation Map ownership;
- factual Governance Only / Mutation Disabled wording;
- Decision Review vs Execution Control separation;
- Production Readiness evidence boundaries;
- automation Notification Channel allowed-use keys; and
- the `kubernetes.deployment.restart` controlled-pilot identity.

The verifier runs in the static quality gate and the Intelligence release surface.
