# KAORI Platform Operations Lock v1.6

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Secret Reveal global-gate and panel-geometry behavior in `KAORI_PLATFORM_OPERATIONS_LOCK_V1_5.md`

## Scope

v1.6 keeps the v1.5 namespace-discovery, HTMX feedback, shared-policy authority, and dark-mode contracts. It reopens only two observed issues: ambiguity between a policy-enabled Namespace and the deployment-level Protected Reveal kill switch, and unequal side-panel geometry in the Secret Reveal workspaces.

## Secret Reveal v1.6 Contract

1. **Global kill switch remains mandatory.** Namespace Policy enablement does not implicitly enable Protected Reveal. `KUBERNETES_SECRET_REVEAL_ENABLED=true` remains an independent deployment-level control and requires application restart/redeployment to take effect.
2. **Disabled-state diagnosis is explicit.** Protected Kubernetes Secret Reveal must distinguish a configured policy from global disablement. When the kill switch is off, the Cluster selector is disabled with explicit global-gate copy rather than looking like an empty target inventory.
3. **Configured policy evidence remains visible.** The Protected Reveal page reports the count of policy-enabled Namespaces even while the global gate is off, so operators can see that policy configuration exists but is not yet consumable.
4. **Global enablement restores the normal selection path.** When the global flag is enabled, a cluster must still pass cluster readiness and have at least one configured enabled Namespace. The target workspace then verifies only those configured Namespaces live before rendering them.
5. **No security bypass.** Global enablement, cluster readiness, Namespace Policy, live Namespace verification, live Secret validation, approval separation, step-up authentication, and one-time reveal revalidation remain mandatory.
6. **Side panels are symmetric at desktop breakpoints.** Administration Readiness Controls/Kubernetes Boundary and Protected Reveal main/context rail use explicit stretch geometry. Shared Context Rail defaults remain unchanged for other pages.
7. **Protected Reveal flow remains compact.** The contextual flow uses shorter operational copy so its height does not dominate the working column.
8. **Dark mode remains neutral-first.** Symmetry changes must not reintroduce hardcoded light surfaces or oversized Bright Violet informational panels.

## Operator Activation

If Namespace Policy is already enabled but Protected Reveal still reports global disablement, set the deployment environment value:

```bash
KUBERNETES_SECRET_REVEAL_ENABLED=true
```

Then restart/redeploy the KAORI web application so Flask reloads configuration. This is intentionally not an in-page toggle.

## Enforcement

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_6_global_gate_and_layout_contract.py
```
