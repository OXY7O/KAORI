# KAORI Draft-to-Ready Single Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep KAORI development/review iteration fast by using Draft PRs to collect findings without governed Full Admission, then pay comprehensive validation once when the final staging candidate becomes Ready for Review and reuse that immutable evidence through staging/main transitions.

**Architecture:** Ordinary issue-branch pushes are not governed Admission triggers. A Draft PR to `kaori/staging` is a collaboration and findings surface and must not acquire the self-hosted CI runner. `ready_for_review` is the first final-candidate Admission event: PR Integration attempts exact evidence reuse and falls back to one Full Admission for a new source tree + validation-authority fingerprint. Staging, promotion, and post-promotion reuse the immutable evidence only when tree, fingerprint, profile version, result, age, and lineage remain valid.

**Tech Stack:** GitHub Actions, Python stdlib, Bash, Docker/Compose, pytest release contracts.

**Spec:** `docs/superpowers/specs/2026-08-30-progressive-ci-evidence-reuse-design.md`

## Global Constraints

- Keep Issue → issue-linked branch → Draft PR → findings/review → Ready for Review → `kaori/staging` → explicit Local UAT → governed `main` promotion.
- Keep all existing Full Admission quality/security gates and code-health ceilings `800 / 160 / 30 / 8`.
- A different source tree always requires new comprehensive evidence.
- A different validation-authority fingerprint always requires new comprehensive evidence.
- Missing, stale, failed, skipped, cancelled, malformed, ambiguous, wrong-profile, wrong-tree, wrong-fingerprint, or unprovable-lineage evidence must fail closed to Full Admission.
- Local UAT remains explicit human acceptance; CI may never fabricate it.
- Draft PR open/synchronize activity must not acquire the self-hosted runner for governed Admission.
- A source change after Ready invalidates prior evidence for the new tree; substantial remediation should return the PR to Draft before the next final candidate.
- Fast transition hard acceptance ceiling is 5 minutes excluding unrelated self-hosted-runner queue delay.
- Duplicate-pytest optimization inside Full Admission is out of scope for this change.

---

### Task 1: Lock Draft PR / Ready Admission policy in RED contracts

**Files:**
- Create: `tests/contracts/release/test_draft_pr_admission_boundary_contract.py`
- Modify: `tests/contracts/release/test_progressive_ci_admission_contract.py` only if an existing invariant needs extension.

**Interfaces:**
- Consumes: `.github/workflows/quality.yml`, delivery workflow, approved spec, this plan.
- Produces: source-level regression contract for the Draft → Ready boundary.

- [x] **Step 1: Write the failing Draft/Ready contract**

The contract requires:

```python
assert "      - ready_for_review" in workflow
assert "      - converted_to_draft" in workflow
assert "github.event.pull_request.draft == false" in workflow
assert "draft pr" in delivery.lower()
assert "ready for review" in delivery.lower()
```

- [x] **Step 2: Confirm the pre-change source violates the contract**

Before implementation, current `quality.yml` contains `ready_for_review` but lacks `converted_to_draft` and the non-draft job guard; current governance/spec/plan also lack the explicit Draft PR authority wording. The RED condition is therefore the intended missing behavior, not a pre-existing unrelated failure.

- [ ] **Step 3: Implement Tasks 2–5 only after the RED boundary is established**

### Task 2: Prevent Draft PRs from acquiring the governed CI runner

**Files:**
- Modify: `.github/workflows/quality.yml`

**Interfaces:**
- Draft PR events: workflow may be instantiated by GitHub, but no self-hosted job may run.
- Ready/non-draft PR events: existing validation-profile routing remains authoritative.

- [ ] **Step 1: Keep review-relevant pull request events**

Use the staging/main PR event set:

```yaml
pull_request:
  branches:
    - main
    - kaori/staging
  types:
    - opened
    - synchronize
    - reopened
    - ready_for_review
    - converted_to_draft
```

`converted_to_draft` is retained so the same concurrency group can cancel a validation run if a Ready PR is explicitly returned to Draft.

- [ ] **Step 2: Gate the first self-hosted job on non-draft PR state**

`validation-profile` must use the equivalent of:

```yaml
if: >-
  ${{ github.event_name != 'pull_request' ||
      (github.event.pull_request.draft == false &&
       github.event.pull_request.head.repo.full_name == github.repository) }}
```

All expensive jobs already depend on `validation-profile`, so no separate Draft condition is duplicated across every job.

- [ ] **Step 3: Preserve concurrency cancellation**

Keep the PR-ref concurrency key and `cancel-in-progress` semantics. Returning an active PR to Draft must cancel obsolete candidate validation rather than leave expensive runner work executing.

### Task 3: Preserve one Full Admission per tree + authority fingerprint

**Files:**
- Modify only if required: `scripts/ci_admission.py`
- Modify only if required: `scripts/ci_admission_policy.py`
- Test: `tests/contracts/release/test_progressive_ci_admission_contract.py`

**Interfaces:**
- Evidence identity: `source tree SHA + validation-authority fingerprint + profile version`.
- Transition resolver: PR Integration / Staging Integration / Promotion / Post-promotion are fast candidates and fail closed to Full.

- [x] **Step 1: Keep profile version `3` and deterministic authority fingerprint**

Authority includes tracked Git identities for workflows, CI helpers, requirements, release validation contracts, delivery authority, Docker/runtime authority, and `scripts/verify_*`.

- [x] **Step 2: Keep exact evidence validation**

Evidence must be PASS, Full profile, current profile version, exact source tree, exact authority fingerprint, within the age window, from KAORI `quality.yml`, and contain all required Full gate successes.

- [x] **Step 3: Keep secure artifact retrieval**

Initial authenticated calls are HTTPS `api.github.com`. Cross-host artifact redirects must remain HTTPS and drop GitHub `Authorization`; HTTP downgrade fails closed.

- [x] **Step 4: Keep transition lineage verification**

A different merge commit SHA is allowed only when parent/tree evidence proves that staging/main preserved the admitted source tree.

### Task 4: Align canonical delivery governance with Draft → Ready

**Files:**
- Modify: `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- Modify: `docs/superpowers/specs/2026-08-30-progressive-ci-evidence-reuse-design.md`

**Interfaces:**
- Draft PR is review/findings authority, not Admission authority.
- Ready/non-draft staging candidate is the first governed comprehensive Admission boundary.

- [ ] **Step 1: Update lifecycle wording**

Canonical sequence becomes:

```text
Issue
  -> issue-linked branch
  -> focused development checks
  -> Draft PR to kaori/staging
  -> collect/repair findings
  -> Ready for Review
  -> PR Integration
  -> Full Admission once for a new tree/fingerprint, otherwise exact reuse
  -> merge kaori/staging
  -> Staging Integration reuse + fresh smoke
  -> explicit Local UAT
  -> promotion to main
```

- [ ] **Step 2: Define Ready-tree changes**

If source changes after Ready, old evidence cannot authorize the new tree. Significant repairs return the PR to Draft until the next candidate is review-clean; a later Ready candidate receives exactly the validation required by its identity.

- [ ] **Step 3: Preserve review/UAT authority**

No Critical/Important review finding may remain unresolved before merge. Local UAT stays human and explicit.

### Task 5: Verify the final closed-PR branch before reopening

**Files:**
- No new production files.

- [ ] **Step 1: Review final branch diff against `kaori/staging`**

Expected scope is CI routing/evidence policy, delivery/spec/plan governance, and release contracts only. No KAORI application/report behavior change is admitted.

- [ ] **Step 2: Confirm comprehensive gate inventory is unchanged**

Required Full jobs remain:

```text
Static, Architecture, and Governance
Secrets, SAST, Dependencies, and Workflow Security
Functional and Integration Tests
Frontend Reproducibility
Production Image, Container Security, Runtime, and DAST
KAORI CI Admission
```

- [ ] **Step 3: Confirm Draft contract is structurally GREEN**

The workflow source must contain `converted_to_draft` and the non-draft `validation-profile` guard; docs/spec/plan must describe Draft PR and Ready for Review.

### Task 6: Reopen PR #60 into Draft and collect findings without Full Admission

**Files:**
- PR metadata/body only.

- [ ] **Step 1: Rewrite PR #60 body using the KAORI PR evidence order**

The PR must describe both the artifact-redirect security repair and the revised single-Admission Draft/Ready authority, with explicit out-of-scope and UAT sections.

- [ ] **Step 2: Reopen #60 and immediately convert it to Draft**

Because `reopened` may instantiate a workflow while the PR is momentarily non-draft, `converted_to_draft` plus the existing concurrency group must cancel obsolete work. The Draft-state workflow itself must schedule no self-hosted validation job.

- [ ] **Step 3: Perform structured diff review while Draft**

Review workflow routing, evidence identity, redirect security, lineage, delivery governance, and release contracts. Repair all Critical/Important findings while Draft.

- [ ] **Step 4: Confirm no unresolved review threads**

Do not move to Ready while a Critical/Important issue remains.

### Task 7: Ready the final candidate and pay Full Admission once

**Files:**
- No source changes after the final Ready transition unless a new finding requires returning to Draft.

- [ ] **Step 1: Mark #60 Ready for Review**

The `ready_for_review` event starts the governed candidate validation.

- [ ] **Step 2: Verify expected routing**

For the new profile-v3 tree/fingerprint, PR Integration should attempt evidence lookup, report `FALLBACK`, and execute one comprehensive Full Admission because no matching evidence exists yet.

- [ ] **Step 3: Require Full Admission PASS and immutable evidence artifact**

Do not merge on a partial/failed/cancelled result.

- [ ] **Step 4: If source changes after Ready, enforce identity invalidation**

Old evidence must not be reused for the changed tree. For substantial remediation, convert PR back to Draft before additional implementation/finding collection.

### Task 8: Merge to staging and prove fast evidence reuse

**Files:**
- No new source changes.

- [ ] **Step 1: Merge #60 to `kaori/staging` only after review and final Admission are clean**

Use the governed KAORI merge strategy and exact accepted head.

- [ ] **Step 2: Verify Staging Integration**

The staging merge must preserve the admitted tree/fingerprint and prove parent lineage. Heavy comprehensive groups are `REUSED`; only fresh deterministic smoke runs.

- [ ] **Step 3: Measure wall clock**

Hard acceptance is `<=5 minutes` excluding unrelated runner queue blockage. Unexpected Full fallback is a #55 defect and must be investigated before progression.

### Task 9: Complete UAT and promotion authority

**Files:**
- GitHub evidence/metadata only unless a real defect is found.

- [ ] **Step 1: Sync the exact machine-verified staging SHA into the Local Dev Container**

- [ ] **Step 2: Record explicit human UAT acceptance**

- [ ] **Step 3: Promote accepted `kaori/staging` to `main` through a governed PR**

Promotion/post-promotion reuse valid immutable evidence + fresh smoke when the accepted lineage remains exact.

- [ ] **Step 4: Synchronize Issue/PR/Project metadata and close #55 only after the full delivery boundary completes**

## Completion Evidence

#55 is complete only when:

- ordinary issue-branch pushes do not trigger governed Full Admission;
- Draft PR open/synchronize/converted-to-draft activity does not acquire the self-hosted runner;
- findings are collected and repaired while Draft;
- `ready_for_review` is the final staging-candidate Admission boundary;
- the final #60 tree/fingerprint receives comprehensive Full Admission once;
- immutable evidence is published and validated;
- staging integration reuses that evidence with fresh smoke in `<=5 minutes` excluding unrelated queue delay;
- a later eligible transition also reuses exact evidence;
- fail-closed mismatch behavior remains contract-proven;
- comprehensive quality/security gate inventory and thresholds are unchanged;
- Local UAT remains explicit;
- timing, exact run/evidence identity, review state, and Project metadata are recorded in Issue #55.
