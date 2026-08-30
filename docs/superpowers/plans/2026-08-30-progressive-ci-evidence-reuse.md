# KAORI Progressive CI Evidence Reuse Implementation Plan

> Issue: #55 — Reduce CI lead time with exact admission evidence reuse
> Approved design: `docs/superpowers/specs/2026-08-30-progressive-ci-evidence-reuse-design.md`
> Base authority: `kaori/staging@864dbfbf60a7a4f361b526a215b60a7076b868f3`

## Objective

Replace repeated full-pipeline recomputation with one comprehensive Full Admission per exact implementation tree plus short, fail-closed evidence-verification profiles for staging/main transitions. Preserve all current quality/security gates and make operator output concise, structured, and human readable.

## Guardrails

- No application behavior changes.
- No code-health threshold changes; retain `800 / 160 / 30 / 8`.
- No removal of Ruff, formatter, Pyright, architecture, contracts, migrations, functional/integration, frontend, security, image scan, runtime, or DAST from Full Admission.
- Missing/stale/failed/skipped/ambiguous evidence or identity mismatch must produce `FALLBACK` to Full Admission.
- CI/workflow/security/dependency/runtime/migration/validation-contract changes force Full Admission.
- Local Dev Container UAT remains explicit human acceptance.
- Output vocabulary: `PASS`, `FAIL`, `SKIP`, `REUSED`, `FALLBACK`.

## Task 1 — Lock progressive-routing and evidence policy in RED contracts

**Files**
- Create: `tests/contracts/release/test_progressive_ci_admission_contract.py`

**RED behaviors**
1. Delivery governance version is `2.0` and describes Full Admission + exact evidence reuse.
2. Workflow contains an explicit profile-resolution job before expensive jobs.
3. Branch push routes to Full Admission.
4. PR to `kaori/staging` routes to PR Integration when exact reusable evidence is valid.
5. Push to `kaori/staging` routes to Staging Integration when merge lineage/tree is equivalent.
6. PR `kaori/staging -> main` routes to Promotion.
7. Push to `main` routes to Post-promotion.
8. Sensitive paths force Full Admission.
9. Failed/skipped/cancelled/missing evidence cannot be reused.
10. Full Admission still contains all six current authoritative gate names.

**Verification**
- Push RED-only commit.
- Confirm KAORI CI Static Foundation fails only on the intended progressive-CI contract assertions.
- Record exact run/head in Issue #55.

## Task 2 — Implement deterministic CI policy helper

**Files**
- Create: `scripts/ci_admission.py`
- Extend: `tests/contracts/release/test_progressive_ci_admission_contract.py`

**Responsibilities**
- `resolve_profile(...)` from event/ref/base/head/changed paths.
- `is_sensitive_change(paths)`.
- `validate_evidence(...)` using exact commit/tree/profile version and required-gate conclusions.
- `validate_staging_lineage(...)` using expected merge parents and tree equivalence.
- `validate_promotion_lineage(...)` / post-promotion parent/tree checks.
- Render concise operator summary records.
- CLI subcommands expose deterministic JSON/key-value output for Actions.

**TDD cycle**
- RED: pure-function tests for each decision/fallback reason.
- GREEN: minimal helper implementation.
- Refactor only after focused tests pass.

## Task 3 — Add immutable Admission evidence publication and lookup

**Files**
- Update: `.github/workflows/quality.yml`
- Update: `scripts/ci_admission.py`
- Extend: `tests/contracts/release/test_progressive_ci_admission_contract.py`

**Evidence schema**
- profile schema/version (`2`);
- result `PASS`;
- source commit SHA;
- source tree SHA;
- workflow run ID / attempt;
- event/ref identity;
- required Full Admission gate results;
- upstream Full Admission run ID for reused profiles;
- timestamp.

**Implementation**
- Full Admission final job writes evidence JSON only after every existing required gate succeeds.
- Upload evidence as a run-scoped artifact.
- Fast-profile resolver uses read-only GitHub Actions API access to locate successful evidence for the exact source authority.
- Download/parse with Python stdlib; never trust artifact name alone.
- Evidence lookup failures return `FALLBACK`, never PASS.

**Security**
- Workflow permissions remain minimal: `contents: read`, add only `actions: read` where required.
- No write token is required for evidence lookup.

## Task 4 — Route workflow into Full vs fast profiles

**Files**
- Update: `.github/workflows/quality.yml`
- Extend contracts.

**Workflow structure**
1. `validation-profile` — checkout, compute changed paths/tree/lineage, resolve requested profile and execution mode (`full` or `fast`).
2. Existing expensive jobs run only when execution mode is `full`.
3. `integration-smoke` runs only for validated fast profiles.
4. Final `KAORI CI Admission` accepts either:
   - successful comprehensive Full Admission, or
   - successful exact-evidence verification + fast smoke.
5. Any resolver uncertainty switches execution mode to `full` rather than failing open.

**Sensitive path families**
- `.github/workflows/**`
- `.github/ci/**`
- `scripts/quality_gate.sh`
- `scripts/ci_admission.py`
- `tests/contracts/release/**` when validation authority is changed
- `requirements/**`
- `Dockerfile*`, compose/runtime/security authority
- `migrations/**`
- governance delivery/CI authority documents

## Task 5 — Add a short fresh integration smoke profile

**Files**
- Update: `scripts/quality_gate.sh`
- Extend: `tests/contracts/release/test_progressive_ci_admission_contract.py`

**New phase**
- `--smoke`

**Fresh checks**
- Python syntax/import/reachability sanity;
- migration graph sanity;
- release/delivery contract subset;
- explicit E2E smoke suite;
- no full functional suite, frontend rebuild, image rebuild/scan, or DAST when comprehensive evidence is exactly reusable.

These expensive conclusions are shown as `REUSED`, not silently skipped.

## Task 6 — Make Actions output human readable

**Files**
- Update: `scripts/quality_gate.sh`
- Update: `.github/workflows/quality.yml`
- Extend: `tests/contracts/release/test_verifier_output_readability_contract.py`
- Extend: `tests/contracts/release/test_progressive_ci_admission_contract.py`

**Step Summary contract**
- Result
- Profile
- Commit SHA / tree SHA
- Evidence source / Full Admission run
- Fresh checks
- Reused coverage
- Duration
- First actionable failure
- Next action

**Log presentation**
- Raw verbose verifier/pytest output stays inside clearly named GitHub log groups or diagnostics artifacts.
- Success path prints concise group results/counts rather than dozens of unrelated prose PASS lines.
- Failure path surfaces the first failing check/test and source path before raw detail.
- Pytest keeps short traceback and final counts.

## Task 7 — Update governance authority to v2.0

**Files**
- Update: `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- Update: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Changes**
- Lifecycle wording becomes Full Admission → exact evidence reuse where valid → staging integration → UAT → promotion.
- Replace absolute `never reuse conclusions` rule with exact immutable evidence policy.
- Define fallback conditions and sensitive-change comprehensive validation.
- Keep Local UAT and review authority unchanged.
- Governance version `2.0`.

## Task 8 — GREEN verification on #55 implementation branch

Run canonical CI via branch push and require:
- Static / Architecture / Governance PASS;
- Security PASS;
- Functional/Integration PASS;
- Frontend PASS;
- Production Image/Runtime/DAST PASS;
- final Full Admission PASS;
- evidence artifact emitted for exact final branch tree;
- operator Step Summary readable and complete.

Because #55 changes CI authority itself, the #55 implementation branch and sensitive staging/main transitions intentionally receive Full Admission.

## Task 9 — Governed staging integration and rollout proof

1. Open governed PR to `kaori/staging` after final branch Full Admission.
2. Sensitive-path detection must force Full Admission for the #55 PR itself.
3. Merge only after review/CI/no-drift.
4. Post-merge staging must also remain comprehensive if sensitive-change policy requires it.
5. Perform explicit Local Dev Container UAT focused on Actions summary/readability and unchanged application behavior.
6. Promote to `main` through governed PR and complete post-main verification.

## Task 10 — Prove the optimized fast path before #39

Use a small #55-owned non-sensitive rollout probe after the new workflow is authoritative:

1. Create a temporary issue-linked probe branch from current staging with one meaningful non-sensitive rollout-evidence documentation change.
2. Branch push receives Full Admission and publishes exact evidence.
3. PR to staging must resolve `PR Integration` and reuse that exact Full Admission.
4. Verify duration and Step Summary.
5. Merge and prove `Staging Integration` reuse.
6. Deliberately execute a controlled evidence/tree mismatch scenario and prove resolver reports `FALLBACK` and selects Full Admission.
7. Record before/after timing in #55.

Only after both reuse and fallback are proven may #39 become active.

## Completion Evidence

#55 is complete only when:
- comprehensive gate inventory is unchanged;
- progressive profiles are deterministic and contract-tested;
- evidence identity is exact and fail-closed;
- governance v2.0 is aligned;
- human-readable output is visibly improved;
- real fast-path reuse is demonstrated;
- deliberate mismatch fallback is demonstrated;
- staging/UAT/main lifecycle passes;
- measured lead time is recorded against the old ~25-minute repeated-run history.
