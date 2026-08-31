# KAORI Progressive CI and Admission Evidence Reuse Design

## Status

Revised and approved in chat on 2026-08-31 under Issue #55.

This revision supersedes the earlier rule that validation-authority changes must repeat Full Admission at every affected transition. The governing principle is now:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

A change to validation authority creates a new fingerprint and therefore requires one fresh Full Admission for that tree/fingerprint pair. Once that pair is admitted, later staging/main transitions reuse the immutable evidence instead of recomputing the same comprehensive gates.

## Problem

KAORI has been paying approximately 20–30 minutes for comprehensive CI repeatedly across work-branch push, staging PR, staging merge, promotion PR, and main merge. On the single self-hosted runner this can become 1–2 hours of machine waiting even when later transitions contain the same source tree and the same validation contract.

That behavior is safe but not information-efficient. Re-running the same Static, Security, Functional/Integration, Frontend, Production Image, Runtime, and DAST conclusions against equivalent content does not materially increase confidence.

## Goals

- Keep Issue → branch → PR → staging → Local UAT → main governance intact.
- Make development iteration fast by not running governed Full Admission on ordinary issue-branch pushes.
- Run comprehensive Full Admission once for each immutable source tree under one validation-authority fingerprint.
- Reuse that evidence through staging/main transitions when tree, fingerprint, result, age, and lineage are valid.
- Fail closed to Full Admission whenever equivalence cannot be proven.
- Preserve all existing comprehensive quality and security gates.
- Keep Local UAT explicit and human.
- Target fast transition wall-clock at 2–5 minutes.

## Non-goals

- No quality threshold increase.
- No security, runtime, migration, DAST, test, frontend, architecture, type, or code-health gate removal from Full Admission.
- No evidence reuse across a different source tree.
- No evidence reuse across a different validation-authority fingerprint.
- No fabricated UAT.
- No mutable `latest` evidence.
- No duplicate-pytest optimization in this change; that remains a separate performance improvement after #55 rollout proof.

## Delivery Model

### Development iteration

Ordinary issue branches remain issue-linked `kaori/<type>-<issue>-<slug>` branches, but GitHub Actions no longer runs the governed Full Admission on every branch push.

During implementation the developer runs focused local checks appropriate to the blast radius using existing KAORI commands and test suites. The expensive governed Admission boundary moves to the staging Pull Request, where the candidate source tree is stable enough for comprehensive validation to be worth the cost.

This intentionally separates:

- **development feedback** — focused and iterative; and
- **governed Admission** — comprehensive and auditable.

### PR to `kaori/staging`

The staging PR is the first governed Admission boundary.

The resolver first looks for reusable Full Admission evidence for the current immutable tree and current authority fingerprint. A normal new source tree will not have that evidence, so the workflow reports `FALLBACK` and runs Full Admission once. An unchanged retry of an already admitted PR may reuse its existing evidence.

### Staging integration

After merge to `kaori/staging`, the merge commit may have a different commit SHA while preserving exactly the same source tree as the admitted PR head.

If all of the following are true, comprehensive validation is reused:

- merge tree equals the admitted tree;
- validation-authority fingerprint equals the admitted fingerprint;
- evidence result is PASS and all required gates succeeded;
- profile version is current;
- evidence is within the accepted age window;
- merge-parent lineage proves the admitted head was integrated without reconstruction.

The transition then runs only fresh integration smoke and produces the machine-verified Local UAT candidate.

### Promotion and post-promotion

Promotion from `kaori/staging` to `main`, and the resulting main merge, reuse the same Full Admission evidence when the accepted tree/fingerprint and lineage remain intact. Fresh smoke still runs at the transition boundary.

A changed tree, changed fingerprint, stale/missing evidence, failed/skipped gate, or ambiguous lineage falls back to comprehensive Full Admission.

## Validation Authority Fingerprint

Evidence identity is:

`source tree SHA + validation authority fingerprint + profile version`

The fingerprint is deterministic and derived from tracked Git identities for validation-authority files. It includes the profile version and tracked blobs/modes for the following authority families:

- `.github/workflows/**`;
- `.github/ci/**`;
- `requirements/**`;
- `scripts/ci_admission.py` and the active Admission helper;
- `scripts/quality_gate.sh`;
- `scripts/verify_*`;
- `tests/contracts/release/**`;
- `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`;
- `Dockerfile*`;
- `docker-compose*`.

Application-only file changes do not change the authority fingerprint, but they change the source tree SHA and therefore still require a new Admission.

Validation-authority changes alter both the tree and fingerprint. They therefore require a fresh Full Admission once, but **do not force another Full Admission at staging/main when the admitted tree/fingerprint is unchanged**.

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
- each authoritative Full Admission gate conclusion.

Artifact names are not trusted as evidence. The JSON payload is parsed and verified.

## Profiles

KAORI retains these governed profiles:

1. **Full Admission** — all comprehensive gates.
2. **PR Integration** — evidence lookup; falls back to Full for a new tree, otherwise reuse + smoke.
3. **Staging Integration** — tree/fingerprint/lineage verification + smoke.
4. **Promotion** — accepted staging tree/fingerprint/lineage verification + smoke.
5. **Post-promotion** — resulting main tree/fingerprint/lineage verification + smoke.

Ordinary issue-branch pushes are development activity, not a governed Admission profile, and are therefore removed from the expensive Actions push trigger.

## Full Admission Gate Inventory

The comprehensive profile remains unchanged and must include:

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
- source identity in the evidence is missing;
- evidence is missing, expired, stale, malformed, or ambiguous;
- any required Full gate is not `success`;
- workflow identity is not KAORI `quality.yml`;
- lineage cannot prove the transition preserves the admitted source.

A reuse rejection produces `FALLBACK` and comprehensive Full Admission. It never silently passes.

## Artifact Download Security

Initial GitHub API requests remain restricted to HTTPS `api.github.com` and may carry the workflow token. GitHub artifact downloads may redirect to signed HTTPS blob storage. The GitHub `Authorization` header must be stripped when the redirect changes host, and non-HTTPS redirects are rejected.

## Expected Lead Time

Normal stable work item:

- development pushes: no governed Full Admission wait;
- staging PR: Full Admission approximately 20–30 minutes once for a new tree/fingerprint;
- staging merge: target 2–5 minutes;
- Local UAT: human time;
- promotion: target 2–5 minutes;
- post-promotion: target 2–5 minutes.

The target is roughly 30–40 minutes of governed machine validation for a normal work item instead of several repeated 20–30 minute runs.

## Rollout Acceptance

#55 is not complete until live evidence proves:

1. a final staging PR source tree receives Full Admission once;
2. the subsequent staging merge with the same tree/fingerprint reuses that evidence and completes within 5 minutes excluding unrelated runner queue blockage;
3. a later eligible transition also reuses evidence;
4. a controlled tree/fingerprint/evidence mismatch is proven fail-closed without manufacturing an unnecessary long live run when deterministic contract evidence is sufficient;
5. all comprehensive gates remain present and successful;
6. Local UAT remains explicit.

Only after that proof may #39 proceed under the optimized delivery path.
