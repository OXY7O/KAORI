# Tenant external adoption, Release & Re-adopt — implementation admission matrix

**Review snapshot:** 2026-10-09 · **Not a UAT result**  
**Authority:** #736/#983, #982/#991, #996/#690, #999, #1000 and
`docs/engineering/KAORI_DELIVERY_WORKFLOW.md`.  
**Base under evaluation:** `kaori/review/staging-uat` with integrated
Draft PR #1016 (issue #1015), incorporating issue-branch authorities #1009,
#1010, #1011, #1012 and #1014. The integration is one reviewable source
candidate, but it is **not merged into the review branch**, not exact-head
Developer Check/Full Admission approved, and not accepted for DevContainer UAT.
The native handoff, Capsule attachment, Intelligence and remediation portions
remain governed by their original implementation issues.

## Capability-first lifecycle

```text
Native/Capsule provider (authoritative)
  -> explicit Discovery / live provider inventory
  -> Admit as New Tenant OR Attach Namespace to Existing Tenant
  -> commit adopted Tenant/Namespace generation and provider evidence
  -> Tenant Registry / Access / Drift / Intelligence read committed KAORI state
  -> governed Release Review + dependency inventory
     -> observation-only + zero active dependencies
        -> explicit operator confirmation -> provider-preserving Released -> re-discovery / Re-adopt
     -> KAORI-mutated allocation / access
        -> if Namespace mutation provenance=true and provider inventory is
           verified, a handoff *plan* may be prepared; unknown provenance blocks
        -> fingerprint-bound handoff plan -> independent KAORI approval
        -> Native dry-run preview -> external successor reference (unverified)
        -> external operator acts in authoritative provider
        -> provider UID/spec/foreign-metadata read-back (observation only)
        -> BLOCKED: trusted successor acceptance and permitted Release finalizer not yet admitted
```

A Capsule Tenant controller remains the authority for Capsule CR ownership,
namespace membership, quotas and RBAC. Native API server/IdP remain
authoritative for native RoleBindings and authenticated principals.

## Implementation status by scenario

| Scenario | Current code authority | Expected behavior before UAT | Admission |
| --- | --- | --- | --- |
| Native external Namespace → New Tenant | #736, existing adoption | Fresh Discovery, governed preflight and explicit Adopt | Existing capability; recheck regression |
| Native external Namespace → Existing Tenant | #983, merged PR #986 | One cluster/owner/generation; no duplicate Tenant; explicit governed attachment | Existing review-branch code; UAT pending |
| Capsule external Tenant → New Tenant | #736, Capsule adapter | Verify CR UID/provider state/observed allocations, preserve controller authority | Existing capability; UAT pending |
| Capsule Namespace → Existing Tenant | #983, Draft PR #1010 | Discovery and Registry share one attachment service, compare CR and Namespace UID/RV/ownerReference; foreign RBAC unchanged | Draft; focused gates pending |
| Observation-only Release / Re-adopt | #991, merged PR #1005 | Zero dependencies, fresh immutable provider reread, Released lineage then next generation | Narrow path exists; live UAT pending |
| Native KAORI-mutated handoff | #991, Draft PR #1009 | Independent plan/approval; dry-run; successor reference; post-change provider observation; no implicit Released | Provider observation only; trusted successor acceptance **BLOCKED** |
| Capsule KAORI-mutated handoff | #991/#121 | Never infer authority from a Namespace label; verify Capsule owners/rules/CR | Executor/finalizer **BLOCKED** |
| External Native/Capsule RBAC | #996, Draft PR #1014 | Observe foreign principals, compare exact Role permissions to versioned profiles, never auto-create a grant | Read-only preview; identity-admission **BLOCKED** |
| Access Drift → Governance Intelligence | #999, Draft PR #1011 | Use latest committed evidence with valid source freshness, no fabricated effective access proof | Draft; targeted gates pending |
| Access Drift → Remediation planning | #1000, Draft PR #1012 | Source inventory fingerprint/UID and analysis fresh; recommend-only; no auto escalation | Draft; executor **BLOCKED** |

## Required negative/UAT coverage (after code admission)

1. **Authority:** wrong cluster, different Capsule Tenant UID, reused Native
   Namespace UID, terminating resource, stale resourceVersion, wrong
   ownerReference generation, duplicate governance owner, Released-history
   conflict. Capsule Discovery and Adoption Preflight use the same immutable
   Capsule owner UID check as final Attach Submit. New Native/Capsule Tenant
   adoption submits the exact UID/resourceVersion from its explicit Preflight,
   rejecting replaced objects and changed versions; Native Attach to an
   Existing Tenant uses the same preflight UID/resourceVersion binding.
   Native ownership PATCH rechecks adopted Namespace UID, requires provider
   resourceVersion, rejects foreign KAORI Tenant claims, and verifies UID
   after mutation. Every invalid Attach must leave provider and KAORI state
   unchanged; post-patch read-back failures must never claim success.
2. **Non-destructive Release:** active credentials, Access Grants, memberships,
   managed profiles, managed resources and policies must block. All active
   Namespace records require explicitly `provider_mutation_performed=false`
   before observation-only Release. If `true`, an independently reviewed handoff
   *plan* may be prepared from exact provider evidence but must never finalize
   Released; missing/unknown provenance blocks even handoff planning.
   Verify provider Namespace/Capsule CR exists with exact UID after Released.
   Re-adoption must allocate a new generation and retain historical committed
   evidence.
3. **Native handoff:** requestor cannot approve their own plan; expired plan,
   fingerprint mismatch, inconsistent dry-run or mutated spec/labels/
   ownerReferences/finalizers must block. External provider read-back can only
   record observation and must *not* unlock Release.
4. **Capsule owner safety:** external `owners`, `additionalRoleBindings`,
   Tenant rules, Namespace ownerReferences and controller-managed quotas must
   never be overwritten by adoption or observation.
5. **RBAC:** forged/partial KAORI markers, foreign group identities, unknown
   ServiceAccount namespace, wildcard/aggregated/named-resource ClusterRoles
   and overly broad permissions fail closed; exact profile match never
   implies imported identity/effective access.
6. **Intelligence/remediation:** new clean/invalid evidence supersedes old drift;
   timestamps outside admissible windows or new inventory digest changes
   invalidate prior planning. No unattended privilege escalation.
7. **UX and operations:** Violet shared UI, responsive/light/dark, 5-row default
   paging, HTMX/CSRF, accessible forms, toast/error/loading/empty state,
   audit correlations, recoverability, and no live provider reads on normal
   Tenant Registry rendering. Adoption Preflight must explicitly disclose
   admitted Native/Capsule provider writes for New Tenant adoption, while
   Capsule Namespace Attach must disclose read-only provider mirroring and
   no automatic RBAC expansion; operator confirmation must not call a
   provider-mutating action "evidence-only". Validate a failed New Tenant
   provider cutover and a failed DB commit after a possible provider write:
   no pending KAORI Tenant/Namespace record may survive rollback, operational
   failure must identify potential provider residue with submitted preflight
   UID/resourceVersion, and the operator must inspect provider state before
   retry. A CSRF or unsupported-provider failure must not be marked as a
   started provider operation. Native Attach success must attribute provider
   mutation to Namespace evidence, not unchanged Tenant adoption origin.

## Quality gates / evidence checklist

- [ ] Targeted pytest for #983/#991/#996/#999/#1000 and relevant merged
      release/adoption/identity regression suites.
- [ ] Ruff, Pyright, DjLint, Prettier and repository `verify_*` gates.
- [ ] Developer Check PASS on exact candidate according to approved workflow.
- [ ] Full Admission PASS on frozen final candidate.
- [ ] Cross-PR integration conflicts resolved, exact merged source SHA recorded.
- [ ] Local DevContainer Visual QA + Native and Capsule provider security tests.
- [ ] Human UAT acceptance with screenshots, logs, audit and provider read-back.
- [ ] Only then normal `kaori/staging` admission and later promotion policy.

The review branch is not an admission authority by itself. The current
GitHub Actions `developer-check.yml` listens for PRs targeting
`kaori/staging`, not review sandbox branches; do not equate a missing run with PASS.

**Unresolved architecture acceptance:** no provider-verified external successor
identity/consent mechanism is agreed for real ownership transfer. This
cannot be satisfied by two internal KAORI approvals, an operator-submitted
ticket string, a Kubernetes ownership label, or a successful server dry-run.
The final external-acceptance and mutation/recovery contract must be admitted
under #991/#690 before code may mark a KAORI-mutated Tenant Released.
