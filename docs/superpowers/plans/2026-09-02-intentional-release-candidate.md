# Intentional Release Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple normal `kaori/staging` integration from Release Candidate publication and introduce an explicit, idempotent, human-friendly RC cut workflow.

**Architecture:** `kaori/staging` remains comprehensive integration authority. Before the release workflow reaches the default branch, an RC is deliberately requested by advancing the dedicated `kaori/rc-request` control branch to the exact admitted staging SHA; after the workflow exists on `main`, `workflow_dispatch` is also available. Both paths resolve and verify the current staging head, require exact successful staging quality evidence, prevent duplicate RC consumption for an already-published source, keep image security/runtime gates blocking, and create a GitHub prerelease with operator-readable metadata.

**Tech Stack:** GitHub Actions YAML, Bash, Git/GitHub REST API, Docker, Trivy, Pytest contract tests.

**Spec:** GitHub Issue #98.

## Global Constraints

- Work branch validation is path-aware Developer Check only.
- Comprehensive KAORI CI remains authorized only on `kaori/staging`.
- Normal staging pushes must not mint RC numbers, push RC images, create RC tags, or create GitHub prereleases.
- `kaori/rc-request` is a control ref only; its triggering SHA must equal the current `kaori/staging` head.
- `workflow_dispatch` remains available for the later state where the workflow exists on the default branch, and must be run against `kaori/staging`.
- RC publication must remain fail-closed on exact staging CI success.
- Trivy HIGH/CRITICAL, runtime validation, and DAST remain blocking before registry push.
- Registry credentials remain repository secrets and must never be printed.
- No `latest` image tag.
- Stable promotion remains governed by #51 and explicit UAT.
- Do not rebuild an accepted image during stable promotion.

---

### Task 1: Lock deliberate RC trigger contract

**Files:**
- Modify: `tests/contracts/release/test_staging_image_publish_contract.py`

**Interfaces:**
- Consumes: `.github/workflows/publish-staging-image.yml` source text.
- Produces: contract proving deliberate RC creation and absence of staging-push auto publication.

- [x] **Step 1: Write the failing trigger contract**
  - Require future `workflow_dispatch:` support.
  - Require `kaori/rc-request` as the only push-based release control branch.
  - Reject `kaori/staging` as a publication trigger.
  - Require current staging SHA resolution/validation.

- [x] **Step 2: Run Developer Check and observe RED**
  - Initial valid RED: Developer Check #132, where all preceding gates and 2,264 focused tests passed before the intentional RC trigger contract failed against the legacy staging-push workflow.

- [ ] **Step 3: Replace trigger/guards with deliberate RC cut semantics**
  - `kaori/rc-request` control-branch trigger for the pre-main release train.
  - `workflow_dispatch` for the later default-branch state.
  - Resolve/verify current `kaori/staging` SHA and reject stale/non-authoritative RC requests.

- [ ] **Step 4: Run Developer Check and verify trigger contract GREEN**

### Task 2: Make RC creation idempotent and human-friendly

**Files:**
- Modify: `tests/contracts/release/test_staging_image_publish_contract.py`
- Modify: `.github/workflows/publish-staging-image.yml`

**Interfaces:**
- Consumes: exact staging SHA, Git tag history, registry configuration, successful `quality.yml` staging push evidence.
- Produces: at most one published RC per exact accepted source SHA plus a GitHub prerelease page.

- [x] **Step 1: Write failing idempotency/prerelease contracts**
  - Require detection of an existing `vX.Y.Z-rc.N` tag/release whose target SHA equals the accepted staging SHA.
  - Require stop before any new RC number or registry push when that source is already published.
  - Require GitHub Release API publication with `prerelease: true` and human-readable body sections.

- [ ] **Step 2: Run Developer Check and observe final RED**

- [ ] **Step 3: Implement duplicate-source guard**
  - Fetch tags/releases after exact staging checkout.
  - Return success without new publication when an exact source already has a valid prerelease.
  - Fail closed if a source has an RC tag but its GitHub prerelease evidence is missing, rather than consuming another RC number.

- [ ] **Step 4: Implement GitHub prerelease evidence**
  - Build release notes from commit/validation/artifact evidence available to the workflow.
  - Include source SHA, candidate image, immutable digest, quality run, security/runtime/DAST result, migration/data indicator, UAT pending state, known limitations, and stable-promotion rule.
  - Create the GitHub prerelease only after immutable registry digest evidence exists.

- [ ] **Step 5: Run Developer Check and verify GREEN**

### Task 3: Freeze and integrate #98

**Files:**
- No additional production files unless contract cleanup is required.

**Interfaces:**
- Produces: immutable work-branch source candidate suitable for PR to `kaori/staging`.

- [ ] **Step 1: Compare branch against exact staging base and confirm only intended files changed**
- [x] **Step 2: Open governed Draft PR #101 to `kaori/staging` with #98 linkage**
- [ ] **Step 3: Confirm work-branch Developer Check PASS and no comprehensive KAORI CI on work branch**
- [ ] **Step 4: Review PR threads/submissions and freeze exact source SHA**
- [ ] **Step 5: Merge to staging only after the workflow can no longer auto-publish an RC from that staging merge**
- [ ] **Step 6: Verify post-merge staging KAORI CI; do not cut a new RC yet**
