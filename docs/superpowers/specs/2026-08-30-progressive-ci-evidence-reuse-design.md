# KAORI Progressive CI and Admission Evidence Reuse Design

## Status

Design approved in chat on 2026-08-30. Storage Analysis #38 has completed its governed staging/UAT/main lifecycle, so this design is now active under expedited CI-governance Issue #55.

## Problem

KAORI currently runs effectively the same comprehensive validation repeatedly across a governed delivery lineage:

1. work-branch push;
2. pull request to `kaori/staging`;
3. post-merge `kaori/staging` push;
4. promotion pull request from `kaori/staging` to `main`;
5. post-merge `main` push.

The current workflow is intentionally conservative, but on a single self-hosted runner this repeats expensive source linting, type checking, contract/functional/integration tests, frontend reproducibility, production-image build and scan, runtime validation, and DAST even when the source tree already has exact full-admission evidence and has not changed.

The result is high lead time with little additional information. KAORI needs to preserve the same quality and security authority while avoiding redundant recomputation.

## Goals

- Run comprehensive KAORI Admission once for an exact implementation source tree.
- Reuse that exact evidence only when SHA/tree lineage proves equivalence.
- Escalate automatically to full Admission whenever equivalence cannot be proven.
- Keep Local Dev Container UAT as the human acceptance boundary.
- Keep code-health, static, type, security, functional/integration, frontend, production-image, runtime, migration, and DAST coverage authoritative.
- Make CI output readable and human friendly enough that an operator can understand result, authority, duration, failure, and next action without reading raw logs.
- Reduce routine branch-to-main validation wait from repeated 20–30 minute full runs to one full run plus short integrity/smoke gates.

## Non-goals

- No quality threshold increase.
- No removal of security scanning, runtime validation, DAST, Pyright, Ruff, contract tests, functional/integration tests, frontend reproducibility, migration validation, or code-health checks from the comprehensive Admission profile.
- No reuse across a different source tree.
- No implicit UAT or automated fabrication of human acceptance.
- No weakening of PR review or unresolved-thread gates.
- No dependence on mutable `latest`-style artifacts.

## Admission Model

KAORI will use five validation profiles.

### 1. Full Admission

Authority: exact implementation source tree.

Runs all existing authoritative gates:

- Static, Architecture, and Governance;
- Secrets, SAST, Dependencies, and Workflow Security;
- Functional and Integration Tests;
- Frontend Reproducibility;
- Production Image, Container Security, Runtime, and DAST;
- final KAORI Admission assertion.

A successful full run publishes immutable admission evidence containing at minimum:

- source commit SHA;
- source tree SHA;
- workflow run ID and attempt;
- workflow/ref identity;
- each required gate conclusion;
- timestamp;
- validation-profile version.

The evidence is valid only for the exact tree it records.

### 2. PR Integration Gate

Used for a pull request from an already admitted implementation branch to `kaori/staging`.

It verifies:

- PR head SHA is unchanged;
- a successful Full Admission exists for that exact head/tree;
- PR base is the expected staging authority;
- changed-file scope is still represented by the admitted head;
- required review state remains clean;
- merge result can be evaluated without source reconstruction.

It then runs a short deterministic integration check rather than repeating all expensive gates. If exact prior evidence cannot be located or any lineage check is ambiguous, the workflow falls back to Full Admission.

### 3. Staging Integration Gate

Used after merge to `kaori/staging`.

It verifies:

- staging merge commit parents are the expected previous staging commit and admitted implementation head;
- merge tree is equivalent to the admitted implementation tree when the branch was based on that exact staging parent;
- no unexpected source reconstruction occurred.

It runs fast integration/runtime smoke checks. If merge-tree equivalence cannot be proven, it falls back to Full Admission.

After this gate succeeds, the exact staging SHA becomes the machine-verified Local Dev Container UAT candidate.

### 4. Promotion Gate

Used for `kaori/staging -> main` after explicit Local UAT acceptance.

It verifies:

- PR head is the exact UAT-accepted staging lineage selected for promotion;
- main target has not introduced incompatible drift;
- staging source evidence remains valid;
- promotion contains no reconstructed application source.

Ambiguous or changed source escalates to Full Admission.

### 5. Post-promotion Gate

Used after merge to `main`.

It verifies that the resulting main merge contains the exact accepted staging tree and expected parent lineage, then performs a short production integrity/runtime smoke check. Ambiguous or changed source escalates to Full Admission.

## Evidence Reuse Safety Rules

Evidence reuse is permitted only when all required identity checks pass.

- SHA alone is not enough when a merge commit is involved; tree identity must also be checked.
- A different tree always invalidates reuse.
- A missing, cancelled, skipped, neutral, or failed gate never counts as reusable evidence.
- Workflow/profile version changes invalidate older evidence when the validation contract changes.
- Any governance, CI, security, dependency, Docker/runtime, migration, or validation-contract change forces Full Admission for the affected transition.
- Manual workflow dispatch defaults to Full Admission.
- Reuse failures fail closed into comprehensive validation; they do not silently pass.

## Workflow Routing

The workflow resolves an explicit validation profile from event and branch context.

- governed implementation branch push: `full`;
- PR to `kaori/staging`: `pr-integration`, with fail-closed fallback to `full`;
- push to `kaori/staging`: `staging-integration`, with fail-closed fallback to `full`;
- PR to `main` from `kaori/staging`: `promotion`, with fail-closed fallback to `full`;
- push to `main`: `post-promotion`, with fail-closed fallback to `full`;
- manual dispatch: default `full`.

The expensive Full Admission remains the source of truth. Faster profiles are evidence-verification and smoke layers, not replacements for missing full evidence.

## Human-Friendly Test and CI Output

The operator-facing output must be concise, structured, and actionable.

Every validation profile writes a GitHub Step Summary with:

1. **Result** — PASS / FAIL / FALLBACK.
2. **Profile** — Full Admission, PR Integration, Staging Integration, Promotion, or Post-promotion.
3. **Authority** — exact commit SHA and tree SHA.
4. **Evidence** — reused full run ID when applicable, or `fresh full validation`.
5. **Duration** — total profile duration and major gate durations where available.
6. **Coverage** — what was executed fresh and what was reused.
7. **Failure** — first actionable failing command/test/check, not a generic `job failed`.
8. **Next action** — one short operator instruction.

Vocabulary is limited to `PASS`, `FAIL`, `SKIP`, `REUSED`, and `FALLBACK` for operator status wording.

Pytest output keeps concise tracebacks and final counts/failing test names. Verbose diagnostic output remains available in collapsible raw log groups or artifacts; the primary summary must not dump thousands of lines.

Example success summary:

```text
PASS — KAORI Staging Integration
Profile         Staging Integration
Authority       dffd49d5... / tree 3bc5c0ac...
Evidence        REUSED Full Admission #346
Fresh checks    merge lineage, migration/import smoke, E2E smoke
Reused coverage static, security, full tests, frontend, image scan, runtime, DAST
Duration        4m 12s
Next action     Sync exact staging SHA for Local UAT
```

Example failure summary:

```text
FAIL — KAORI PR Integration
Profile         PR Integration
First failure   tests/reports/test_storage_analysis_pdf_template.py::test_missing_evidence_is_explicit
Reason          expected `Not Available`, received `0%`
Next action     Repair Storage missing-evidence behavior
```

## Testing Strategy

Changes are implemented with TDD.

RED contracts first lock:

- event-to-profile routing;
- exact SHA/tree evidence requirements;
- fail-closed fallback to Full Admission;
- no reuse of failed/skipped/ambiguous evidence;
- forced Full Admission for CI/security/dependency/runtime/migration/validation-contract changes;
- staging merge-tree equivalence rules;
- promotion/post-promotion exact-lineage rules;
- readable Step Summary fields and actionable failure output;
- unchanged comprehensive quality/security gate inventory.

GREEN implementation then updates the workflow, CI policy helper, and quality-gate presentation without changing application behavior.

Verification includes:

- contract tests for workflow routing/evidence policy;
- existing release/delivery governance contracts;
- workflow/security validation;
- a forced Full Admission on the implementation branch;
- proof that a following non-sensitive staging PR uses the faster profile only when exact evidence is valid;
- proof that intentional evidence mismatch falls back to Full Admission;
- human review of the Step Summary for readability.

## Governance Update

`docs/engineering/KAORI_DELIVERY_WORKFLOW.md` moves from `full CI at every transition and never reuse conclusions` to explicit **Full Admission + exact evidence reuse** authority.

The governance authority remains conservative:

- every implementation source tree receives comprehensive Full Admission;
- later stages may reuse conclusions only under exact commit/tree identity and successful immutable evidence checks;
- changed or ambiguous source triggers comprehensive validation;
- sensitive validation-authority changes trigger comprehensive validation;
- Local UAT remains explicit and human;
- main promotion remains governed and reviewable.

The delivery workflow governance version increments to `2.0` because this changes CI authority.

## Expected Lead Time

Typical no-regression path on the existing single runner:

- Full Admission: approximately 20–30 minutes once;
- PR Integration: target 2–5 minutes;
- Staging Integration: target 3–5 minutes;
- Local UAT: human time;
- Promotion: target 1–3 minutes;
- Post-promotion: target 2–4 minutes.

Target machine validation is approximately 30–40 minutes per normal work item, with a P95 objective of no more than 45 minutes, rather than several repeated full pipelines totaling roughly two hours or more.

## Rollout

The first rollout must prove both paths before #39 starts:

1. exact admitted lineage reuses Full Admission evidence in a non-sensitive staging integration path;
2. deliberate evidence/tree mismatch escalates to Full Admission.

A small #55-owned rollout probe may be used after the sensitive CI-governance implementation itself is integrated, because changes to CI/workflow/governance files intentionally force Full Admission and therefore cannot prove the fast path by themselves.

Only after both paths are demonstrated should later Phase 1 work use the optimized pipeline by default.
