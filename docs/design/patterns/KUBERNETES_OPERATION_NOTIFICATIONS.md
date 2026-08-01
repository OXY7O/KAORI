# Kubernetes Operation Notifications


## TLS update validation gate

Single and bulk TLS Secret updates use the validated-operation contract. Update actions start disabled, successful validation enables them, and any certificate-file or target-selection change invalidates the previous validation. Bulk validation requires at least one valid selected target. Apply endpoints continue to validate server-side; the disabled action is an operator workflow guard, not the security boundary.

## TLS update success reset

A successful single or bulk TLS Secret update must queue its success notification and then perform a full-page redirect back to the owning update workspace. The redirect resets uploaded certificate/key files, selected targets, preview content, modal state, and the validated-operation gate. The queued toast is displayed after the refreshed page loads.

Partial-success or failed bulk operations remain in place so the operator can inspect failed targets and retry without losing diagnostic evidence.
