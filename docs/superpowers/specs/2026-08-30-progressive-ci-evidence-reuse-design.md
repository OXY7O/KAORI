# KAORI Draft-to-Ready Progressive CI and Admission Evidence Reuse Design

## Status

Revised and approved in chat on 2026-08-31 under Issue #55.

This revision makes the collaboration boundary explicit:

> **Draft PR = collect findings without governed Full Admission. Ready for Review = final staging-candidate Admission boundary.**

The evidence rule remains:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

A source-tree or validation-authority change creates a new evidence identity and requires one fresh Full Admission. Once that exact tree/fingerprint/profile tuple is admitted, later staging/main transitions reuse the immutable evidence instead of recomputing the same comprehensive gates.

## Problem

KAORI previously paid approximately 20–30 minutes for comprehensive CI repeatedly across issue-branch pushes, staging PR activity, staging merge, promotion PR, and main merge. On the single self-hosted runner this created long lead time and queue contention even when later transitions preserved the same content.

The rollout also exposed a second inefficiency: opening a staging PR while implementation and review findings are still evolving causes expensive validation to start before the candidate is actually ready. Every subsequent fix changes the source tree and makes the previous Full Admission obsolete.

The required model therefore separates three activities:

1. **development feedback** — focused checks while coding;
2. **Draft PR review/findings** — collaboration without governed Full Admission;
3. **Ready candidate Admission** — comprehensive, auditable validation of the intended final staging candidate.

## Goals

- Keep Issue → branch → Draft PR → findings/review → Ready for Review → staging → Local UAT → main governance intact.
- Do not run governed Full Admission on ordinary issue-branch pushes.
- Do not acquire the self-hosted CI runner for Draft PR open/synchronize activity.
- Use `ready_for_review` as the first comprehensive staging-candidate Admission event.
- Run comprehensive Full Admission once for each immutable source tree under one validation-authority fingerprint and profile version.
- Reuse that evidence through staging/main transitions when tree, fingerprint, result, age, profile, and lineage are valid.
- Fail closed to Full Admission whenever equivalence cannot be proven.
- Preserve all existing comprehensive quality/security/runtime/DAST gates.
- Keep Local Dev Container UAT explicit and human.
- Target eligible fast transitions at 2–5 minutes wall-clock excluding unrelated runner queue delay.

## Non-goals

- No application feature or report semantic/layout change.
- No code-health threshold increase; defaults remain `800 / 160 / 30 / 8`.
- No security, runtime, migration, DAST, test, frontend, architecture, type, or code-health gate removal from Full Admission.
- No evidence reuse across a different source tree.
- No evidence reuse across a different validation-authority fingerprint/profile version.
- No automated or fabricated Local UAT.
- No mutable `latest` evidence.
- No duplicate-pytest optimization inside Full Admission in this change.

## Delivery Model

### 1. Issue branch development

Normal work starts from the governed Issue on an isolated issue-linked branch. Ordinary issue-branch pushes are development activity, not governed Admission events.

The developer uses existing focused KAORI checks/tests appropriate to the blast radius. This keeps iteration responsive without weakening the eventual comprehensive candidate validation.

### 2. Draft PR to `kaori/staging`

A Draft PR is opened while implementation review and structured findings are still being collected.

Draft PR responsibilities:

- expose the complete candidate diff for review;
- collect architectural, security, reliability, test, governance, and maintainability findings;
- repair findings while the PR remains Draft;
- keep Issue/PR traceability and metadata current.

Draft PR open/synchronize activity is **not** a governed Admission boundary and must not acquire the self-hosted runner for Full Admission or fast smoke.

GitHub may instantiate a workflow record for supported PR events, but the first self-hosted job is guarded by `pull_request.draft == false`. Therefore a Draft event produces no KAORI validation job.

`converted_to_draft` is included in the event set so returning a Ready PR to Draft creates the same PR concurrency group and cancels obsolete candidate validation.

### 3. Ready for Review — final staging candidate

When Critical/Important findings are resolved and the branch is intended to be admitted as the complete staging candidate, the PR is marked **Ready for Review**.

The `ready_for_review` event starts `PR Integration`.

The resolver looks for reusable Full Admission evidence for:

`source tree SHA + validation authority fingerprint + profile version`

For a normal new candidate no matching evidence exists, so PR Integration reports `FALLBACK` and runs comprehensive Full Admission once. A successful run publishes immutable Admission evidence for that exact identity.

An unchanged retry may reuse the exact evidence. If source changes after Ready, prior evidence cannot authorize the new tree. Significant remediation should return the PR to Draft until the next candidate is review-clean; the later Ready candidate then receives the validation required by its own identity.

### 4. Merge and Staging Integration

Merge to `kaori/staging` occurs only when:

- final Ready candidate Admission is PASS;
- structured review has no unresolved Critical/Important finding;
- no source drift occurred after the accepted candidate.

The merge commit SHA may differ from the admitted PR head while preserving exactly the same source tree. Comprehensive validation is reused only when:

- merge tree equals the admitted tree;
- validation-authority fingerprint equals the admitted fingerprint;
- profile version is current;
- evidence result is PASS and every required Full gate succeeded;
- evidence is within the accepted age window;
- merge-parent lineage proves the admitted head was integrated without reconstruction.

Staging Integration then runs only fresh deterministic integration/runtime smoke and produces the machine-verified Local UAT candidate.

### 5. Explicit Local Dev Container UAT

The exact machine-verified `kaori/staging` lineage is synchronized into the Local Dev Container. UAT remains explicit human acceptance and is never inferred from CI.

### 6. Promotion and Post-promotion

A governed `kaori/staging` → `main` PR promotes only the exact UAT-accepted staging lineage. Promotion and post-promotion reuse the same immutable Full Admission evidence when tree/fingerprint/profile/lineage remain valid and execute fresh integrity smoke.

Any changed tree, changed fingerprint, stale/missing evidence, failed/skipped gate, or ambiguous lineage falls back to comprehensive Full Admission.

## Validation Authority Fingerprint

Evidence identity is:

`source tree SHA + validation authority fingerprint + profile version`

The fingerprint is deterministic and derived from tracked Git identities for validation-authority files, including:

- `.github/workflows/**`;
- `.github/ci/**`;
- `requirements/**`;
- `scripts/ci_admission.py` and active Admission policy helper;
- `scripts/quality_gate.sh`;
- `scripts/verify_*`;
- `tests/contracts/release/**`;
- `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`;
- `Dockerfile*`;
- `docker-compose*`.

Application-only changes leave the fingerprint unchanged but change the source tree, so they still require a new Full Admission once. Validation-authority changes alter both tree and fingerprint; after the new pair passes Full Admission once, later equivalent transitions reuse it.

## Evidence Schema

A successful Full Admission artifact records at minimum:

- result `PASS`;
- profile `full`;
- validation profile version;
- source commit SHA;
- source tree SHA;
- validation-authority fingerprint;
- workflow run ID and attempt;
- workflow/ref identity;
- timestamp;
- every authoritative Full Admission gate conclusion.

Artifact names are never trusted as evidence. The JSON payload is parsed and verified.

## Profiles

KAORI retains five governed profiles:

1. **Full Admission** — comprehensive validation for a new evidence identity or fail-closed fallback.
2. **PR Integration** — Ready/non-draft staging candidate evidence lookup; new identity falls back to Full, admitted identity uses reuse + smoke.
3. **Staging Integration** — tree/fingerprint/lineage verification + fresh smoke.
4. **Promotion** — exact UAT-selected staging tree/fingerprint/lineage verification + fresh smoke.
5. **Post-promotion** — resulting main tree/fingerprint/lineage verification + fresh integrity smoke.

Draft PR activity is deliberately outside these execution profiles because no self-hosted validation job is scheduled while `draft == true`.

## Workflow Event and Runner Contract

The workflow retains PR events required for lifecycle control:

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

The first self-hosted job must require either a non-PR event or a same-repository PR whose `draft` state is false.

Consequences:

- opening a Draft PR: no KAORI self-hosted job;
- pushing findings/fixes while Draft: no KAORI self-hosted job;
- marking Ready: governed candidate validation starts;
- synchronizing a Ready PR: new identity is re-evaluated and old evidence cannot authorize changed source;
- converting Ready back to Draft: obsolete run is cancelled through the existing PR concurrency group and no Draft job runs.

## Full Admission Gate Inventory

The comprehensive profile remains unchanged and includes:

- Static, Architecture, and Governance;
- Secrets, SAST, Dependencies, and Workflow Security;
- Functional and Integration Tests;
- Frontend Reproducibility;
- Production Image, Container Security, Runtime, and DAST;
- final KAORI CI Admission assertion and immutable evidence publication.

## Fail-closed Rules

Reuse is rejected if any of the following is true:

- source tree differs;
- authority fingerprint differs;
- profile version differs;
- source identity is missing;
- evidence is missing, expired, stale, malformed, or ambiguous;
- any required Full gate is not `success`;
- workflow identity is not KAORI `quality.yml`;
- lineage cannot prove the transition preserves the admitted source.

A rejection produces `FALLBACK` and comprehensive Full Admission. It never silently passes.

## Artifact Download Security

Initial authenticated GitHub API requests are restricted to HTTPS `api.github.com`. Artifact archive retrieval may redirect to signed HTTPS blob storage. When the redirect changes host, the GitHub `Authorization` header is removed while non-secret request headers may remain. Any non-HTTPS redirect fails closed.

This fixes the rollout defect observed after PR #59 routed correctly to PR Integration but the blob endpoint rejected the forwarded GitHub Bearer credential with HTTP 401.

## Human-Readable CI Evidence

Operator output uses only `PASS`, `FAIL`, `SKIP`, `REUSED`, and `FALLBACK` status vocabulary and exposes:

1. result;
2. profile;
3. exact source SHA/tree;
4. evidence source/run;
5. duration;
6. fresh coverage;
7. reused coverage;
8. first actionable failure when failed;
9. one next action.

Raw diagnostics remain retained separately. Readability must never suppress a validation assertion.

## Expected Lead Time

Normal stable work item:

- branch development: no governed Full Admission wait;
- Draft PR review/finding cycles: no governed Full Admission wait;
- Ready staging candidate: approximately one 20–30 minute Full Admission for a new tree/fingerprint;
- staging merge: target 2–5 minutes;
- Local UAT: human time;
- promotion: target 2–5 minutes;
- post-promotion: target 2–5 minutes.

The model intentionally spends comprehensive machine time only when the candidate is intended to be accepted.

## Rollout Acceptance

#55 is complete only when live and deterministic evidence proves:

1. Draft PR open/synchronize/converted-to-draft activity does not acquire the self-hosted runner;
2. a final Ready staging PR tree/fingerprint receives Full Admission once;
3. the subsequent staging merge preserves that tree/fingerprint, reuses the evidence, and completes within 5 minutes excluding unrelated runner queue delay;
4. a later eligible transition also reuses evidence;
5. controlled tree/fingerprint/evidence mismatch remains fail-closed;
6. all comprehensive gates and thresholds remain present;
7. structured review has no unresolved Critical/Important finding before staging merge;
8. Local UAT remains explicit and is recorded on the exact staging lineage.

Only after that proof may #39 proceed under the optimized delivery path.
