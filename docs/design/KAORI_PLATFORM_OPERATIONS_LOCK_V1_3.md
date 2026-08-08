# KAORI Platform Operations Lock v1.3

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Secret Reveal presentation and live-source behavior in `KAORI_PLATFORM_OPERATIONS_LOCK_V1_2.md`

## Scope

Platform Operations v1.2 remains the Jobs & Executions baseline. v1.3 reopens only **Kubernetes Administration → Secret Reveal** for readiness correctness, live-source evidence, render efficiency, mutation guardrails, and presentation-density refinements. The top-level information architecture remains unchanged.

## Secret Reveal v1.3 Contract

1. **Readiness has three visible prerequisites.** Cluster Credential, Encryption at Rest, and Metadata Audit are all visible. Cluster Credential is read-only and reflects primary kubeconfig availability.
2. **Live source failures never become Missing evidence.** `Missing` is valid only after a successful live namespace refresh. Failed refreshes produce `Unknown` live state and a visible source-unavailable callout.
3. **Search/filter/pagination reuse a namespace snapshot.** The initial tab load, cluster switch, and explicit Refresh may call the Kubernetes namespace-list API. Search, filtering, pagination, page-size changes, and save-response rendering reuse the current snapshot.
4. **Mutation safety remains live.** Enabling Step-up or Approval Required still performs `verify_live_namespace()` and requires full cluster readiness. Existing enabled access can always be changed to Disabled.
5. **Protection Posture stays synchronized.** Readiness and namespace policy mutations update top-level protected-cluster, enabled-namespace, and selected-cluster posture through HTMX out-of-band fragments.
6. **Kubernetes Boundary and Activation Boundary use clear surfaces.** Solid Violet guidance panels are retired; Violet remains an accent and primary-action color.
7. **Protection Boundary is compact.** The page uses the concise Step-up Authentication → Independent Approval → Namespace Policy → Kubernetes RBAC flow instead of four verbose guidance cards.
8. **Namespace table terminology is operationally precise.** `Live Namespace` replaces `Live Source`; row state is Available/Missing/Unknown; `Set Policy` replaces Configure.
9. **Row Save follows dirty-state hierarchy.** Save is neutral/disabled until the policy selection changes, then becomes the Violet primary action.
10. **Immediate mutation feedback remains standard.** Save Readiness and Set Policy continue to use shared operational toast feedback plus durable Operational Activity. Background progress toast behavior is not introduced.
11. **Existing Platform Operations locks remain frozen.** v1.0–v1.2 navigation, execution semantics, Job Configuration behavior, shared components, dark-mode tokens, and cleanup contracts remain unchanged.

## Enforcement

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
pytest -q tests/contracts/kubernetes
pytest -q tests/contracts/jobs
```
