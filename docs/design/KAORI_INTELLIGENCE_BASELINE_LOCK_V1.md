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

- Application-layer orchestration surface under `app/automation_control/`.
- Read surface requires `intelligence.view`.
- Mutation routes may exist for continued implementation, but the default is fail-closed.
- `AUTOMATION_CONTROL_MUTATIONS_ENABLED` must resolve false when absent.
- Environment-level enablement of that guard is deliberately deferred until the feature-complete review.
- Disabled mutation attempts return **Automation Mutation Disabled** feedback and must not execute the operation callback.
- The current read posture is **Governance Only**. `Reserved Plan` is not used for implemented Automation Control read/evidence surfaces.
- Internal exception text must not be exposed to the user.

## Deferred / non-locking feature work

The following may remain incomplete without invalidating this baseline lock:

- Server recommendation/evidence providers.
- HCI recommendation/evidence providers.
- Automation decision execution, resolver mutation, dead-letter requeue, deployment policy
  mutation, operational control mutation, and readiness-stage mutation.
- Additional external signal/provider enrichments.

Those state-changing capabilities must stay visibly disabled/fail-closed until a later feature-complete review supplies provider validation, behavior tests, security regression, rendering contracts, and E2E/integration evidence as applicable. Implemented Automation Control read/evidence surfaces use factual Governance Only wording rather than Reserved Plan.

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
