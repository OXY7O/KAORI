# Domain 16 — Kubernetes Resolver Adapter Foundation

## Objective

Introduce the first live provider adapter behind the Domain 10 resolver boundary without enabling broad autonomous remediation. The initial allowlisted action is `kubernetes.deployment.restart`, implemented as a controlled pod-template annotation patch.

## Safety sequence

1. Resolve the canonical Kubernetes connection for the decision cluster.
2. Enforce protected and allowlisted namespace boundaries.
3. Execute a Kubernetes `SelfSubjectAccessReview` for `patch` on `apps/deployments`.
4. Read and snapshot deployment UID, resourceVersion, generation, and previous restart annotation.
5. Reject stale caller resourceVersion when supplied.
6. send the exact patch to Kubernetes with `dryRun=All`.
7. Persist the dry-run plan through the existing resolver journal.
8. Re-read UID and resourceVersion immediately before mutation.
9. Apply the same patch with field manager `kaori-resolver`.
10. Re-read the deployment and verify the expected restart annotation.
11. Return a snapshot-backed rollback reference.

## Guardrails

- Only `kubernetes.deployment.restart` is supported.
- `kube-system`, `kube-public`, and `kube-node-lease` are always denied.
- An optional explicit namespace allowlist can narrow access further.
- Missing service-account permission blocks dry-run before any mutation call.
- UID or resourceVersion drift after dry-run blocks execution.
- Execution cannot proceed from a fabricated or rejected dry-run result.
- The shared resolver service remains provider-neutral; provider code lives under `app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api`.

## Rollback boundary

The adapter records the previous restart annotation and a canonical snapshot hash. The returned reference is audit evidence for a later governed rollback adapter. Domain 16 does not automatically perform rollback and does not claim that restarted pods can be restored to their previous runtime state.

## Deployment

Apply after Domain 15. No database migration is required. Register the adapter only after Kubernetes connections are ready and the KAORI service account has the intended namespace-scoped patch permission. Keep the resolver route disabled until focused tests and a non-production dry-run pass.

## Validation

```bash
pytest -q \
  tests/resolver/test_kubernetes_resolver_adapter.py \
  tests/contracts/resolver/test_domain16_kubernetes_adapter_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Unregister the adapter first, stop `resolver-execution` workers, verify that no deployment restart journal is queued or running, then remove the Domain 16 files and revert the Kubernetes client authorization API addition. No database downgrade is required.
