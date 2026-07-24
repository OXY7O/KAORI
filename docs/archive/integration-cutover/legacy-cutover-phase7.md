# Legacy Cutover Phase 7 — Guarded Data Reconciliation

Phase 7 reconciles database state before destructive schema removal. It does not drop tables or columns.

The command `flask --app run:app reconcile-integration-legacy` is dry-run by default. It:

- merges duplicate/orphan canonical identities into an unambiguous provider identity;
- moves canonical bindings and runtime observations before deleting a duplicate identity;
- deletes empty canonical identities that have no provider record, binding, or observation;
- deletes legacy provider bindings/config rows only after an equivalent canonical binding is verified;
- clears `clusters.kubeconfig` only after a non-empty `KubernetesConnection.kubeconfig` is verified.

Any ambiguous identity or unreconciled legacy row blocks the entire apply transaction.
