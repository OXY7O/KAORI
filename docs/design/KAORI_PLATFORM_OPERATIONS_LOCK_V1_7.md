# KAORI Platform Operations Lock v1.7

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Secret Reveal side-panel geometry and global-gate helper presentation in `KAORI_PLATFORM_OPERATIONS_LOCK_V1_6.md`

## Scope

v1.7 keeps the v1.6 global kill-switch, configured-policy evidence, least-privilege namespace discovery, shared reveal-policy authority, immediate HTMX feedback, and dark-mode contracts. It reopens only the observed visual regression caused by forcing equal-height Secret Reveal panels and the long inline global-gate helper under the Cluster selector.

## Secret Reveal v1.7 Contract

1. **Global kill switch remains mandatory.** `KUBERNETES_SECRET_REVEAL_ENABLED=true` remains a deployment-level control; Namespace Policy enablement does not bypass it.
2. **Configured policy evidence remains visible.** Operators can still see that policy-enabled Namespaces exist while the global gate is off.
3. **Activation guidance is boxed, not inline.** The long global-gate explanation is presented as a compact `Activation Tip` callout inside Reveal Target. The Cluster field no longer carries a multi-line warning paragraph.
4. **Natural-height side panels are restored.** Platform Operations Readiness Controls/Kubernetes Boundary and Protected Reveal main/context rail return to content-driven height. They must not use page-specific `items-stretch`, `h-full`, `flex-1`, or Context Rail fill overrides solely to force symmetry.
5. **Shared Context Rail returns to its canonical API.** `layout_classes(width='default')` owns the split and defaults to `xl:items-start`; `rail_classes()` owns rail spacing only.
6. **Compact Protected Reveal flow remains.** v1.6 copy-density improvements are retained even though forced height is removed.
7. **Dark mode remains neutral-first.** Activation guidance uses semantic/shared surfaces and does not introduce hardcoded light surfaces or oversized Violet informational blocks.
8. **Security behavior is unchanged.** Cluster readiness, Namespace Policy, live Namespace verification, live Secret validation, approval separation, step-up authentication, and one-time reveal revalidation remain mandatory.

## Enforcement

```bash
python scripts/verify_platform_operations_final_lock.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_7_natural_height_tip_contract.py
pytest -q tests/contracts/jobs
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
```
