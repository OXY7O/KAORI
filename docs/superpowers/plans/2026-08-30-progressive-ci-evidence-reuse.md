# KAORI Single Full Admission Evidence Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure one comprehensive Full Admission is paid once per immutable source tree + validation-authority fingerprint, while ordinary issue development avoids repeated 20–30 minute GitHub Actions waits.

**Architecture:** Ordinary `kaori/<type>-<issue>-<slug>` branch pushes are removed from the governed Actions push trigger; development feedback remains focused/local. The staging PR becomes the first governed Admission boundary. Full Admission evidence is keyed by source tree, validation-authority fingerprint, and profile version, then reused through staging/main when lineage proves the admitted tree was preserved.

**Tech Stack:** GitHub Actions, Python stdlib, Bash, Docker/Compose, pytest contracts.

**Spec:** `docs/superpowers/specs/2026-08-30-progressive-ci-evidence-reuse-design.md`

## Global Constraints

- Keep Issue → branch → PR → `kaori/staging` → Local UAT → `main` governance.
- Keep all existing Full Admission quality/security gates.
- A different source tree always requires new comprehensive evidence.
- A different validation-authority fingerprint always requires new comprehensive evidence.
- Missing/stale/failed/skipped/ambiguous evidence or lineage must fail closed to Full Admission.
- Local UAT stays explicit and human.
- No duplicate-pytest optimization in this change.
- Fast transition hard acceptance ceiling is 5 minutes excluding unrelated runner queue blockage.
- Do not run governed Full Admission on ordinary issue-branch pushes.

---

### Task 1: Lock single-Admission policy in contracts

**Files:**
- Modify: `tests/contracts/release/test_progressive_ci_admission_contract.py`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: existing `resolve_profile`, evidence and lineage helpers.
- Produces: contracts for branch-trigger scope, tree+fingerprint evidence identity, and transition reuse.

- [ ] **Step 1: Write failing tests**

Lock these behaviors:

```python
assert '      - kaori/staging' in workflow
assert '      - "kaori/**"' not in workflow
assert policy.PROFILE_VERSION == '3'
assert sensitive_pr.execution == 'fast'
assert evidence_tree_and_fingerprint.reusable is True
assert different_fingerprint.reusable is False
```

Also lock that all comprehensive gate names and commands remain present.

- [ ] **Step 2: Verify RED**

Run focused contract tests before implementation. Expected failures are branch trigger still matching `kaori/**`, profile version still `2`, sensitive-path routing still forcing Full, and missing authority fingerprint support.

- [ ] **Step 3: Implement only after RED is observed**

Proceed to Tasks 2–4.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
pytest -q tests/contracts/release/test_progressive_ci_admission_contract.py tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: PASS.

### Task 2: Add deterministic validation-authority fingerprint

**Files:**
- Modify: `scripts/ci_admission.py`

**Interfaces:**
- Produces: `authority_fingerprint_from_entries(entries)` and `compute_authority_fingerprint()`.
- Evidence schema adds `authority_fingerprint`.

- [ ] **Step 1: Implement authority-path classification**

Authority includes `.github/workflows/**`, `.github/ci/**`, `requirements/**`, `scripts/ci_admission.py`, `scripts/quality_gate.sh`, `scripts/verify_*`, `tests/contracts/release/**`, delivery workflow authority, Dockerfiles, and compose files.

- [ ] **Step 2: Build fingerprint from tracked Git identities**

Use `git ls-files -s -z`; hash profile version plus sorted path/mode/blob tuples. Application-only paths are ignored by the fingerprint.

- [ ] **Step 3: Raise profile version to `3`**

The fingerprint contract itself is a validation-authority change, so prior profile-v2 evidence is not reusable.

### Task 3: Make evidence reuse tree + fingerprint based

**Files:**
- Modify: `scripts/ci_admission.py`

**Interfaces:**
- `evidence_reuse_decision(...)` requires current source tree and current authority fingerprint.
- `find_remote_full_evidence(...)` searches source lineage and returns the admitted source SHA from verified evidence.

- [ ] **Step 1: Stop requiring transition commit SHA equality**

The evidence payload must contain a source SHA, but a staging/main merge commit may differ from the admitted PR head SHA when its source tree is identical.

- [ ] **Step 2: Require exact source tree + fingerprint + profile version**

Reject wrong tree, wrong fingerprint, wrong profile, stale evidence, invalid workflow identity, or any required gate not `success`.

- [ ] **Step 3: Preserve artifact download security**

Initial requests stay HTTPS `api.github.com`; cross-host HTTPS artifact redirects strip `Authorization`; non-HTTPS redirects fail closed.

- [ ] **Step 4: Include fingerprint in Full Admission evidence**

`write-evidence` computes the fingerprint from the checked-out source and publishes it in `admission-evidence.json`.

### Task 4: Move Full Admission boundary from issue branch to staging PR

**Files:**
- Modify: `.github/workflows/quality.yml`
- Modify: `scripts/ci_admission.py`

**Interfaces:**
- Issue branch push: no governed Actions trigger.
- PR to `kaori/staging`: candidate `PR Integration`; missing evidence falls back to one Full Admission.
- Staging/main transitions: reuse same tree/fingerprint evidence + fresh smoke.

- [ ] **Step 1: Restrict push trigger**

Use:

```yaml
push:
  branches:
    - kaori/staging
    - main
    - "release/**"
```

Do not trigger governed CI on every `kaori/**` issue-branch push.

- [ ] **Step 2: Remove path-name based repeated-Full routing**

Transition routing no longer says “sensitive file therefore Full at every transition”. Validation-authority changes are represented by the fingerprint: new fingerprint → no reusable evidence → one Full; unchanged fingerprint/tree → reuse.

- [ ] **Step 3: Set workflow profile version to `3`**

Keep all comprehensive jobs unchanged.

- [ ] **Step 4: Keep fast integration smoke unchanged**

Fast transition still runs syntax/architecture/import/migration/release/E2E smoke and reports heavy comprehensive groups as `REUSED`.

### Task 5: Align KAORI governance documentation

**Files:**
- Modify: `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- Modify: `docs/superpowers/specs/2026-08-30-progressive-ci-evidence-reuse-design.md`

**Interfaces:**
- Development feedback and governed Admission are separate boundaries.
- Authority fingerprint is part of reusable evidence identity.

- [ ] **Step 1: Update lifecycle wording**

Issue branch development uses focused local checks; staging PR is the first comprehensive Admission boundary.

- [ ] **Step 2: Update sensitive-change rule**

A validation-authority change requires one Full Admission for the new tree/fingerprint; it does not cause repeated Full runs at staging/main when identity is unchanged.

- [ ] **Step 3: Preserve Local UAT and promotion authority**

No automated UAT or review bypass.

### Task 6: Verify once, then reopen the governed PR once

**Files:**
- No new implementation files.

- [ ] **Step 1: Keep PR #60 closed while assembling commits**

The branch `td55-artifact-redirect-auth-fix` does not match the expensive push trigger. This prevents each documentation/code edit from creating a new 20–30 minute workflow.

- [ ] **Step 2: Review final diff**

Confirm only #55 CI/governance files changed and no comprehensive gate was deleted.

- [ ] **Step 3: Reopen PR #60 once**

The final tree must receive one governed Full Admission. Because profile-v3 evidence does not yet exist for that tree/fingerprint, PR Integration must report FALLBACK and execute Full once.

- [ ] **Step 4: Merge after PASS/review**

After merge, staging push must reuse the PR Full Admission evidence because the merge preserves tree + fingerprint.

- [ ] **Step 5: Measure fast transition**

Hard acceptance: <=5 minutes excluding unrelated runner queue delay. If it falls back to Full unexpectedly, stop and debug evidence/fingerprint/lineage; do not start a new speculative long run.

## Completion Evidence

#55 is complete only when:

- ordinary issue branch pushes no longer trigger governed Full Admission;
- the final staging PR receives Full Admission once for its tree/fingerprint;
- staging integration reuses that evidence;
- a later eligible transition also reuses evidence;
- fast transition execution is <=5 minutes excluding unrelated queue blockage;
- fail-closed mismatch behavior is contract-proven;
- comprehensive gate inventory is unchanged;
- Local UAT remains explicit;
- timing and exact run/evidence identity are recorded in Issue #55.
