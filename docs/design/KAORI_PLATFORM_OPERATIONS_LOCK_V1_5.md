# KAORI Platform Operations Lock v1.5

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Secret Reveal feedback/target-discovery behavior in `KAORI_PLATFORM_OPERATIONS_LOCK_V1_4.md`

## Scope

v1.5 keeps the v1.4 cross-workspace authority and dark-mode contract. It reopens only three observed issues: Namespace Policies pagination copy, immediate feedback delivery for HTMX policy/readiness mutations, and Protected Reveal namespace discovery.

## Secret Reveal v1.5 Contract

1. **Canonical pagination footer.** Namespace Policies renders `Showing … Namespaces`, then the visible `Rows` label and page-size selector.
2. **Immediate HTMX mutation feedback.** Save Readiness and Set Policy persist their activity first, then render the resulting toast through HTMX OOB in the same response. Session-queued feedback is reserved for non-HTMX redirect fallback and must not linger until a later page refresh.
3. **Configured-only target discovery.** Protected Kubernetes Secret Reveal starts from policy-enabled namespace records and verifies only those namespace names live with Kubernetes Namespace `GET`.
4. **No broad Namespace LIST dependency for Protected Reveal.** A namespace that was valid when enabled must not disappear from Protected Reveal merely because the runtime identity lacks broad namespace-list permission.
5. **Live verification remains mandatory.** A configured namespace that no longer exists is excluded. Connectivity, authentication, RBAC, or API errors are surfaced explicitly rather than silently converted to an empty list.
6. **Empty-state diagnostics are explicit.** Protected Reveal distinguishes global disablement, no eligible cluster, no configured namespace policy, and configured-but-not-live namespace states.
7. **Security boundaries remain unchanged.** Global enablement, cluster readiness, namespace policy, live Secret validation, approval separation, step-up authentication, and one-time reveal revalidation remain mandatory.
8. **v1.4 dark-mode contract remains frozen.** Neutral/semantic surfaces remain the default; Bright Violet remains reserved for primary actions and compact accents.

## Enforcement

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_3_refinement_contract.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_4_cross_workspace_contract.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_5_feedback_and_target_contract.py
```
