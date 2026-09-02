# Intentional Release Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple normal `kaori/staging` integration from Release Candidate publication and introduce an explicit, idempotent, human-friendly RC cut workflow.

**Architecture:** `kaori/staging` remains comprehensive integration authority, but RC publication becomes a deliberate `workflow_dispatch` action against the current admitted staging head. The workflow verifies exact staging quality evidence, resolves SemVer only at the RC boundary, blocks duplicate RC creation for an already-published source, publishes the existing registry/digest evidence, and creates a GitHub prerelease with operator-readable metadata.

**Tech Stack:** GitHub Actions YAML, Bash, Git/GitHub REST API, Docker, Trivy, Pytest contract tests.

**Spec:** GitHub Issue #98.

## Global Constraints

- Work branch validation is path-aware Developer Check only.
- Comprehensive KAORI CI remains authorized only on `kaori/staging`.
- Normal staging pushes must not mint RC numbers, push RC images, create RC tags, or create GitHub prereleases.
- RC publication must remain fail-closed on exact staging CI success.
- Trivy HIGH/CRITICAL, runtime validation, and DAST remain blocking before registry push.
- Registry credentials remain repository secrets and must never be printed.
- No `latest` image tag.
- Stable promotion remains governed by #51 and explicit UAT.
- Do not rebuild an accepted image during stable promotion.

---

### Task 1: Lock intentional RC trigger contract

**Files:**
- Modify: `tests/contracts/release/test_staging_image_publish_contract.py`

**Interfaces:**
- Consumes: `.github/workflows/publish-staging-image.yml` source text.
- Produces: contract proving explicit dispatch-only RC creation and absence of staging-push auto publication.

- [ ] **Step 1: Write the failing trigger contract**
  - Require `workflow_dispatch:`.
  - Require accepted staging ref validation.
  - Reject `push:` trigger and push-specific job guard.

- [ ] **Step 2: Run Developer Check and observe RED**
  - Expected: release contract fails because current workflow is staging-push driven.

- [ ] **Step 3: Replace trigger/guards with explicit RC cut semantics**
  - Dispatch-only workflow.
  - Resolve/verify current `kaori/staging` SHA and ensure dispatch runs against staging authority.

- [ ] **Step 4: Run Developer Check and verify trigger contract GREEN**

### Task 2: Make RC creation idempotent and human-friendly

**Files:**
- Modify: `tests/contracts/release/test_staging_image_publish_contract.py`
- Modify: `.github/workflows/publish-staging-image.yml`

**Interfaces:**
- Consumes: exact staging SHA, Git tag history, registry configuration, successful `quality.yml` staging push evidence.
- Produces: at most one RC publication per exact accepted source SHA plus a GitHub prerelease page.

- [ ] **Step 1: Write failing idempotency/prerelease contracts**
  - Require detection of an existing `vX.Y.Z-rc.N` tag/release whose target SHA equals the accepted staging SHA.
  - Require fail/skip before any new RC number or registry push when that source is already published.
  - Require GitHub Release API publication with `prerelease: true` and human-readable body sections.

- [ ] **Step 2: Run Developer Check and observe RED**

- [ ] **Step 3: Implement duplicate-source guard**
  - Fetch tags/releases after checkout.
  - Stop without consuming `NEXT_RC` when exact source already owns an RC.

- [ ] **Step 4: Implement GitHub prerelease evidence**
  - Build release notes from commit/issue/validation/artifact evidence available to the workflow.
  - Include source SHA, candidate image, immutable digest, quality run, UAT pending state, known limitations, and stable-promotion rule.
  - Create GitHub Release using the already-created candidate tag as target.

- [ ] **Step 5: Run Developer Check and verify GREEN**

### Task 3: Freeze and integrate #98

**Files:**
- No additional production files unless contract cleanup is required.

**Interfaces:**
- Produces: immutable work-branch source candidate suitable for PR to `kaori/staging`.

- [ ] **Step 1: Compare branch against exact staging base and confirm only intended files changed**
- [ ] **Step 2: Open governed PR to `kaori/staging` with #98 linkage**
- [ ] **Step 3: Confirm work-branch Developer Check PASS and no comprehensive KAORI CI on work branch**
- [ ] **Step 4: Review PR threads/submissions and freeze exact source SHA**
- [ ] **Step 5: Merge to staging only after the workflow can no longer auto-publish an RC from that staging merge**
- [ ] **Step 6: Verify post-merge staging KAORI CI; do not cut a new RC yet**
