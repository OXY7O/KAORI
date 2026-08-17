# Automation Control Center UI

## Purpose

Automation Control is KAORI's governed bridge from Intelligence evidence to future controlled execution. It does not own rule evaluation, Alertmanager routing, Kubernetes inventory, or provider-specific mutation logic. It coordinates their public contracts into an operator-facing decision, execution-safety, and readiness workspace.

Route: `GET /intelligence/automation-control`

Navigation: **Intelligence → Automation Control**

Ownership boundary: `app/intelligence/automation_control/` remains an application orchestration layer. Knowledge, Intelligence, Resolver, Notification Channels, and Integration domains do not import it. Automation Control may consume their public read/service contracts without creating reverse dependencies.

## Workspace structure

| Workspace | Operator question | Current capability |
|---|---|---|
| Overview | What is the automation control posture right now? | Decision pipeline, pending work, execution activity, execution state, safety controls, production readiness, notification delivery, and the controlled pilot boundary. |
| Runbooks & Bindings | Which tested procedure can this evidence use? | Source-controlled System Runbook Catalog, validated immutable revisions, resolver/verification/recovery contracts, activation state, and environment-specific alert/rule bindings. |
| Decision Review | What is awaiting accountable review? | Non-executable candidates, immutable decisions, policy outcome, approval requirement, evidence hash, scope, and expiry. |
| Execution Control | What can execute and what is happening now? | Resolver registry, deployment policies, safety controls, execution journals, retry state, and dead letters. |
| Production Readiness | What still blocks controlled execution? | Execution gate, registry coverage, deployment policy, readiness evidence, Notification Channel coverage, and ordered rollout stage. |

The old Domain 1–20 Foundation Map is no longer an operator surface. Architecture implementation history remains documented elsewhere; Automation Overview now reports operational control state.

## Current execution boundary

`AUTOMATION_EXECUTION_ENABLED` defaults to false and is exposed in the environment templates as the single infrastructure execution enablement switch. It controls authorization/dispatch/provider mutation, not control-plane governance preparation.

When disabled:

- read/evidence workspaces remain available;
- validated System Runbooks may be activated from the source-controlled catalog and environment bindings remain RBAC/audit governed;
- custom runbook authoring remains locked behind `CUSTOM_RUNBOOK_AUTHORING_ENABLED=false` and is not a supported production capability;
- candidate promotion/dismissal and decision approval/rejection remain accountable governance operations;
- deployment-policy, safety-control, readiness-evidence, and rollout-stage configuration remain writable so the control plane can become ready before execution is enabled;
- resolver authorization and dispatch fail closed with **Infrastructure Execution Disabled** feedback;
- the application authorization service and resolver worker re-check the gate independently; and
- the page posture is **Governance Only / Execution Disabled**.

Dead-letter executions are immutable. Because execution authorization is one-time and the raw token is intentionally not persisted, KAORI never replays a consumed journal. A new attempt begins from fresh evidence and a new candidate/decision lifecycle.


## System Runbook Catalog

Runbook authoring is intentionally asymmetric in the current supported release. KAORI ships tested **System Runbooks** as source-controlled contracts; operators select and activate those contracts instead of editing action JSON in the UI. The initial catalog contains only:

```text
kubernetes.deployment.restart
```

The catalog definition pins the runbook version, resolver action, approval policy, required evidence, required capabilities, compatibility profile, parameter schema, resolver step, post-action verification semantics, and compensating-recovery metadata. Activation validates against a **resolver contract registry** built from adapters shipped in the current KAORI build; it does not require the action to be enabled in the runtime execution registry. This keeps Governance Only preparation independent from `RESOLVER_ENABLED_ACTIONS`. Activation then materializes the definition into the Knowledge persistence model and publishes it after contract validation succeeds. Re-activation is idempotent when the stored immutable revision hash matches. A same-version content mismatch is treated as **Catalog Drift** and fails closed.

System revisions cannot be manually published, withdrawn, or edited through Automation Control. Environment-specific binding and deployment/readiness policy remain operator-owned. Bindings can be enabled or disabled without deletion so candidate generation can be paused while retaining audit evidence. Existing legacy custom records remain visible for audit but cannot receive new bindings while custom authoring is disabled. Production validation rejects `CUSTOM_RUNBOOK_AUTHORING_ENABLED=true` until custom authoring is promoted through simulation, maturity, regression, and security evidence.

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

1. activated source-controlled System Runbook revision and deterministic environment binding;
2. explicit decision policy and approval when required;
3. active cluster/namespace deployment policy;
4. current resolver-registry fingerprint;
5. server-side dry-run evidence;
6. explicit recovery/compensating-action evidence;
7. global/cluster safety-control admission;
8. complete production-readiness checks;
9. execution journal and Activity Audit evidence;
10. Notification Channel coverage for automation lifecycle events; and
11. post-action verification before remediation is considered successful.

## Notification delivery

Notification Channels remains Integrations-owned. Automation Control declares delivery-event contracts:

- `automation.approval_required`
- `automation.decision_approved`
- `automation.decision_rejected`
- `automation.execution_started`
- `automation.execution_completed`
- `automation.execution_failed`
- `automation.verification_failed`

Decision-governance events are queued only after the persisted governance transaction commits. Execution lifecycle producers emit started, verified-completed, execution-failed, and verification-failed events from the resolver lifecycle. Matching validated Notification Channels deliver asynchronously; provider delivery retries are deduplicated by channel and event identity. Notification failure never rewrites the recorded governance or execution outcome. No provider credential or transport code belongs in Automation Control.

## Production-readiness semantics

Readiness is not one boolean. The UI reports these independently:

- Execution Gate
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
| Activate validated System Runbook | `knowledge.runbooks.publish` |
| Create environment binding | `knowledge.runbooks.manage` |
| Custom runbook authoring | Not production-supported; `CUSTOM_RUNBOOK_AUTHORING_ENABLED=false` |
| Promote or dismiss candidate | `intelligence.decisions.create` |
| Approve or reject decision | `intelligence.decisions.approve` |
| Manage policy/control/readiness/dead letters | `intelligence.decisions.execute` |

Permissions do not bypass the infrastructure execution gate or any deployment/readiness/safety admission control.

## Quality contract

`scripts/verify_automation_control.py` locks:

- default fail-closed infrastructure execution behavior;
- explicit `AUTOMATION_EXECUTION_ENABLED=false` default-deny enablement;
- source-controlled System Runbook Catalog ownership with `CUSTOM_RUNBOOK_AUTHORING_ENABLED=false`;
- fail-closed catalog drift detection for immutable System Runbook versions;
- operational Overview ownership rather than Foundation Map ownership;
- factual Governance Only / Execution Disabled wording;
- Decision Review vs Execution Control separation;
- Production Readiness evidence boundaries;
- automation Notification Channel allowed-use keys; and
- the `kubernetes.deployment.restart` controlled-pilot identity.

The verifier runs in the static quality gate and the Intelligence release surface.
