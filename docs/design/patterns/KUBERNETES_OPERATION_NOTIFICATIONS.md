# Kubernetes Operation Notifications



## Background inventory sync feedback

Background inventory synchronization follows one operator feedback contract across TLS and Tenant surfaces:

1. An accepted HTMX dispatch updates the owning inline worker-state surface.
2. Dispatch success does **not** create a persistent Notification Deck item and does not increment the unread badge.
3. Progress remains visible in the owning operational panel while the canonical `JobExecution` is active.
4. Terminal worker completion persists the Notification Deck result and Activity Audit evidence.
5. The terminal polling response emits `kaori:notifications-changed` so the navigation badge refreshes without a manual page reload.
6. Dispatch blockers or failures may still produce immediate error/warning feedback because the requested operation did not start.

The completion notification must describe completed evidence, not merely that a job was queued. Domain-specific counts and exceptions should be included when they materially explain the result.

## TLS update validation gate

Single and bulk TLS Secret updates use the validated-operation contract. Update actions start disabled, successful validation enables them, and any certificate-file or target-selection change invalidates the previous validation. Bulk validation requires at least one valid selected target. Apply endpoints continue to validate server-side; the disabled action is an operator workflow guard, not the security boundary.

## TLS update success reset

A successful single or bulk TLS Secret update must queue its success notification and then perform a full-page redirect back to the owning update workspace. The redirect resets uploaded certificate/key files, selected targets, preview content, modal state, and the validated-operation gate. The queued toast is displayed after the refreshed page loads.

Partial-success or failed bulk operations remain in place so the operator can inspect failed targets and retry without losing diagnostic evidence.
