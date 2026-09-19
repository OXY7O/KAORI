# Operational Action Feedback

## Purpose

Operational Action Feedback is the required interaction contract for persisted actions in KAORI provider workspaces. Every action must produce one user-visible toast and one durable Activity Audit record from the same normalized event payload.

## Core contract

For a same-page mutation:

1. The control sends an HTMX request.
2. The server performs the operation and its server-side guardrails.
3. `record_operational_activity(...)` or the provider wrapper persists the Activity Audit event.
4. The route returns the affected workspace partial.
5. The response includes `components/operation_feedback_oob.html`, which renders `components/operational_toast.html` into `#operational-toast-stack`.
6. The page is not fully reloaded.

For an operation that changes the current resource location, such as successful registration or deletion, the HTMX response uses `HX-Redirect`. The event is queued before navigation so the destination page displays the same persisted feedback.

## Required coverage

The contract applies to mutation or evidence-producing actions:

- Register and update connection.
- Test Connection.
- Full Validation.
- Refresh Runtime.
- Create and remove scope binding.
- Delete provider instance.
- Any future provider action that changes persisted state or operational evidence.

Read-only navigation, tab selection, filter changes, pagination, and history refresh do not create Activity Audit events because they do not change provider state or evidence.

## Response rules

- Same-page success and failure return the smallest complete workspace partial.
- The partial root must have a stable ID and use `outerHTML` when the root itself changes.
- Toast feedback uses out-of-band swap and does not replace the primary target.
- Validation failure, rejected lifecycle operation, and database failure must remain renderable; they must not degrade into an unhandled HTTP 500.
- A non-HTMX request may use redirect fallback, but the normal KAORI control must issue HTMX.

## Audit rules

Every event includes:

- Stable event type.
- Success, warning, or error status.
- Human-readable title, message, and technical detail.
- Provider and instance identity in metadata.
- Scope, binding, runtime, capability, or failure metadata when applicable.
- Action URL to the canonical provider workspace, never a legacy compatibility page.

Toast persistence failure must not reverse a successful provider operation. The failure is logged and the toast states that Activity Audit persistence could not be confirmed.

## Loading and disabled state

- Use `hx-disabled-elt` for the initiating submit control.
- Long-running actions use the established in-panel HTMX loading bar.
- Do not use a full-page loading state for a partial provider operation.
- Do not use browser-native `confirm(...)` for persisted-object deletion.

## Provider normal flow

Metrics Source and Alertmanager use their canonical instance workspace:

- Configuration
- Validation & Capabilities
- Runtime & History
- Bindings & Consumers

Cluster compatibility routes may exist only as redirect or migration boundaries. Normal templates, dependency blockers, and action feedback must point to canonical registration, provider registry, or instance manage routes. Retired product-specific Metrics Source routes are not registered. Canonical registration, provider registry, and instance routes own the workflow without redirects or compatibility wrappers.

## Reference implementation

- `app/templates/components/operation_feedback_oob.html`
- `app/platform_operations/notifications/service.py::record_operational_activity`
- `app/integrations/observability/metrics_source/application/routes.py`
- `app/integrations/observability/alert_source/providers/alertmanager/application/routes.py`


## Toast lifecycle

- The payload contains a unique `feedback_id` and `auto_dismiss_ms`.
- Success defaults to 8 seconds, information to 10 seconds, warning to 12 seconds, and error to persistent.
- Hover and keyboard focus pause the timer.
- Self-dismissing toasts render a compact Violet countdown bar. `operational_toasts.js` owns the timer and animation; templates do not implement per-toast countdown JavaScript.
- The countdown prefers Web Animations API and falls back to a forced-layout transform transition so HTMX/OOB-inserted toasts visibly progress before disappearing.
- The global stack keeps at most four visible toasts and deduplicates the same feedback ID.
- Both authenticated and authentication layouts load `operational_toasts.js`; domain layouts do not own close handlers.
- Background progress remains in Activity Center unless a domain explicitly selects toast delivery for a user-initiated synchronous result.
