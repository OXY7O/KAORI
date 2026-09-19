# KAORI Intelligence Baseline Lock v1

## Lock type

**Baseline lock, not feature-complete lock.**

This lock freezes the current safe Intelligence surface while allowing unfinished
capabilities to continue development behind explicit Reserved Plan/fail-closed boundaries.

## Locked surfaces

### Recommendations

- Active evidence-backed read surface.
- Requires `intelligence.view`.
- HTMX filtering/pagination must preserve results-only ownership.
- Recommendation detail remains the shared side-drawer presentation.

### Rule Catalog

- Active canonical definition surface.
- Requires `intelligence.view`.
- Available, Imported Signal, and Reserved Plan are distinct states.
- Adjacent inline rule definition is the approved detail pattern for catalog records.

### Alert Intelligence

- Active for validated Kubernetes and Object Storage alert-evidence enrichment boundaries.
- Automatic source resolution prefers Alertmanager and falls back to Prometheus `ALERTS` when the selected asset contract allows it.
- Alertmanager remains grouping, inhibition, silence, routing, and raw receiver-delivery owner; KAORI adds interpretation, committed recommendation context, and enriched Notification Channel delivery.
- Server/HCI enrichment remains Reserved Plan until provider contracts are complete.

### Automation Control

- Application-layer orchestration surface under `app/intelligence/automation_control/`.
- Read surface requires `intelligence.view`.
- Candidate promotion/dismissal and decision approval/rejection are active governance operations; they are not infrastructure mutation.
- Approval-required, decision-approved, and decision-rejected events are asynchronously delivered through Notification Channels after the governance transaction commits.
- Governance configuration is operational independently from infrastructure execution: runbooks/bindings, deployment policy, safety controls, readiness evidence, and rollout stages can be prepared while execution remains disabled.
- `AUTOMATION_EXECUTION_ENABLED` must default to false and is explicitly exposed as the single infrastructure execution enablement switch.
- Disabled execution attempts return **Infrastructure Execution Disabled** feedback and must not cross the resolver execution boundary. Authorization and workers re-check the same fail-closed boundary.
- Active alert evidence is materialized independently from outbound notification delivery into deduplicated decision candidates.
- Approval-required decisions enforce maker-checker separation. Dead-letter executions are immutable; consumed one-time authorizations are never replayed.
- The current default posture is **Governance Only**. `Reserved Plan` is not used for implemented Automation Control governance/read/evidence surfaces.
- Internal exception text must not be exposed to the user.

## Deferred / non-locking feature work

The following may remain incomplete without invalidating this baseline lock:

- Server recommendation/evidence providers.
- HCI recommendation/evidence providers.
- Additional resolver action types beyond the controlled Kubernetes Deployment restart pilot.
- Additional provider-specific recovery automation beyond the current manual compensating-recovery evidence contract.
- Additional external signal/provider enrichments.

Deferred provider/action capabilities must remain visibly Reserved Plan or fail-closed until their own feature-complete review supplies provider validation, behavior tests, security regression, rendering contracts, and E2E/integration evidence as applicable. The implemented Automation Control control plane uses factual Governance Only wording when the infrastructure execution switch is disabled.

## Non-negotiable KAORI UI boundary

- Violet canonical Hero and shared context card.
- Shared status labels, loading indicator, tabs/pagination/detail runtime where applicable.
- No page-local inline JavaScript/event handlers.
- No arbitrary typography/raw palette drift.
- Dark mode and accessibility semantics remain part of the locked baseline.

### Notification Delivery Boundary

- Notification Channels is owned by Integrations and is a platform-wide outbound delivery capability.
- Telegram, SMTP email, and Microsoft Teams Workflows are current delivery providers; provider credentials remain encrypted and are never rendered back to clients.
- Alert Intelligence consumes the shared channel layer for governed alert events; it does not own provider credentials or transport adapters.
- Automatic alert delivery requires an enabled channel with a successful test and an Alert Intelligence allowed-use policy.
- The initial alert dispatcher sends first-seen active alert episodes only; resolved-event notification is not yet available.
- Alertmanager remains the raw alert routing and receiver authority; KAORI delivers enriched Intelligence context.
