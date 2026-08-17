# KAORI Platform Operations Lock v1.4

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Secret Reveal cross-workspace and presentation behavior in `KAORI_PLATFORM_OPERATIONS_LOCK_V1_3.md`

## Scope

Platform Operations v1.3 remains the Secret Reveal readiness/live-source baseline. v1.4 reopens only the integration boundary between **Kubernetes Administration → Secret Reveal** and **Kubernetes Operations → Protected Kubernetes Secret Reveal**, plus a minor pagination copy correction and dark-mode surface refinement. No database schema or navigation change is introduced.

## Secret Reveal v1.4 Contract

1. **One policy authority.** Platform Operations configuration and Protected Kubernetes Secret Reveal use `app/kubernetes/operations/secrets/reveal_policy.py` as the shared source of truth for cluster readiness and namespace policy.
2. **Protected Reveal revalidates configuration.** Request creation, approval, and one-time reveal re-check current cluster readiness and namespace policy; a stale request can never bypass a later configuration change.
3. **Configuration mutation invalidates active requests.** Disabling readiness or changing a namespace policy expires matching pending/approved requests before they can be consumed.
4. **Operational target discovery remains live.** Protected Reveal intersects policy-enabled namespaces with current Kubernetes namespaces and reads the selected Secret from the live API before request creation.
5. **Pagination resource labels use Title Case.** My Reveal Requests renders `Request`/`Requests`, and the page-size control uses `Rows Per Page` accessibility text.
6. **Dark mode remains neutral-first.** Informational cards, table headers, row hover states, disabled-feature callouts, and request guidance use semantic/neutral surfaces. Bright Violet is reserved for primary mutation actions and small accents.
7. **v1.3 safety remains frozen.** Tri-state live evidence, snapshot-backed administration filtering, explicit credential readiness, fresh policy-enable verification, OOB posture synchronization, and explicit dirty-state saves remain unchanged.

## Enforcement

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_3_refinement_contract.py
pytest -q tests/contracts/kubernetes/test_secret_reveal_v1_4_cross_workspace_contract.py
```
