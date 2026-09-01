# KAORI Application Delivery Workflow

**Governance Version:** 2.0  
**Scope:** KAORI application repository  
**Authority:** Application-local baseline  
**Future Authority:** Platform Governance / Platform Workflow standards when formally adopted

## Lifecycle

```text
Idea / Request
  -> Issue
  -> Backlog / Refinement
  -> Ready
  -> issue-linked work branch from kaori/staging
  -> Draft PR to kaori/staging
  -> path-aware Developer Check
  -> collect review + Developer Check findings
  -> batch repair
  -> Pre-Ready cheap gate
  -> Ready for Review + frozen final candidate
  -> PR Integration
  -> one fresh Full Admission for a new immutable tree + authority fingerprint
     or exact evidence reuse for an already admitted exact pair
  -> merge commit to kaori/staging
  -> Staging Integration: exact evidence reuse + Fast Smoke
  -> UAT
  -> explicit Local UAT acceptance
  -> when release-bound: immutable OCI image + OCI digest
  -> when release-bound: deploy exact digest to https://kaori.cloud
  -> when release-bound: VPS UAT against accepted staging SHA + digest
  -> Promotion PR kaori/staging -> main
  -> evidence reuse + Fast Smoke
  -> merge commit
  -> Post-promotion integrity
  -> when release-bound: Semantic Versioning release of the same digest without rebuilding
  -> when release-bound: production RUN + rollback evidence
  -> Done
```

KAORI uses a closed-loop delivery model. Product ideas, operational findings, defects, technical debt, monitoring signals, and user feedback return to the backlog as governed work items.

The essential delivery rule is:

> **Develop cheaply in Draft, batch repair findings, freeze one Ready candidate, then pay Full Admission once.**

Full Admission is the final-candidate admission boundary. It is not the normal development/debug loop.

## Human-Readable GitHub Standard

GitHub history is a long-lived engineering record. Titles, branches, commits, Pull Requests, comments, and CI evidence must be readable without reconstructing intent from source code.

### Metadata authority

GitHub-native and GitHub Project fields are the metadata authority. Issue and PR bodies **must not** recreate those fields in a `Project Metadata` table or another duplicate metadata block.

Applicable Issue metadata belongs in GitHub-native surfaces: assignees, Project membership, Status, Sprint, Native Issue Type, Priority, Story Points, Milestone, canonical labels, native relationships, and Development links. Applicable PR metadata belongs in reviewers, assignees, labels, Project/Status/Sprint/Milestone where supported, and Development linkage to the governing Issue.

When connected tooling cannot mutate a Project/custom field or relationship, report the exact missing field and intended value to the maintainer. Do not duplicate unavailable metadata into the body as a workaround.

### Issue titles

Native GitHub Issue Type is the type authority. Do not repeat the type in the title. Use sentence case, describe one outcome/problem, and omit a trailing period.

### Issue body

Every work item should make the following understandable to a reviewer:

1. Context / problem / outcome.
2. In scope and explicitly out of scope.
3. Testable acceptance criteria.
4. Dependencies and relationships.
5. Security, data, migration, observability, and operational impact where applicable.
6. Verification and UAT requirements.

Chronological execution evidence belongs in Issue comments. Keep the Issue body as the current contract and use comments as the audit timeline.

### Branch names

Normal governed work uses issue-linked temporary branches from the current `kaori/staging` baseline. Canonical patterns include:

```text
kaori/story-<issue>-<slug>
kaori/bug-<issue>-<slug>
kaori/task-<issue>-<slug>
kaori/spike-<issue>-<slug>
kaori/chore-<issue>-<slug>
kaori/tech-debt-<issue>-<slug>
kaori/hotfix-<issue>-<slug>
```

Existing issue-specific `feat-*` branches may complete their current governed delivery, but new work should prefer the canonical patterns above.

### Commit messages

KAORI uses Conventional Commit syntax with the governed Issue reference:

```text
<type>(<scope>): <imperative summary> #<issue>
```

Use one logical change per commit, lowercase type/scope, an imperative concrete summary, no trailing period, and the controlling Issue number.

### Pull Requests

A normal work-branch -> `kaori/staging` Pull Request opens as **Draft**. Draft is the development/review state and deliberately avoids governed Full Admission.

Canonical PR body reading order remains:

```text
Summary
  -> Why
  -> What Changed
  -> Out of Scope
  -> Linked Work
  -> Acceptance Criteria Coverage
  -> Verification Evidence
  -> Security / Migration / Operational Impact
  -> UAT
  -> Artifact / Release Evidence when applicable
  -> Release Impact
  -> Reviewer Checklist
```

Use `Refs #<issue>` while work is moving through staging/UAT. Use `Closes #<issue>` only on the final PR whose successful merge is intended to close the work item.

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

`kaori/working` is retired only after issue #10 proves all required commits are represented in `kaori/staging`.

## Project Status Model

GitHub Project `Status` is the lifecycle authority:

1. `Inbox` — captured but not yet triaged.
2. `Backlog` — accepted for consideration/refinement.
3. `Ready` — Definition of Ready satisfied.
4. `In Progress` — implementation or remediation underway.
5. `Review` — Draft/Ready PR review, Developer Check, CI, and integration assessment are active.
6. `UAT` — integrated staging evidence is ready for explicit human acceptance; release-bound work remains here while artifact/VPS acceptance or final promotion is pending.
7. `Done` — applicable acceptance and Definition of Done are satisfied.

`workflow:blocked` is exception metadata, not a competing lifecycle Status.

## Definition of Ready

A work item is Ready when scope is understandable, acceptance criteria are testable, design decisions are resolved, dependencies are identified, security/data/migration/observability impacts are considered, expected validation is known, Story Points are assigned when needed, and no unresolved blocker prevents implementation.

## Definition of Done

Code complete and Full Admission are necessary but not sufficient. Applicable completion requires:

- implementation complete;
- changed-behavior tests pass;
- relevant static, architecture, type, frontend, security, integration, runtime, migration, and DAST authorities pass or are reused only through exact accepted evidence;
- documentation/contracts aligned;
- no known regression unresolved;
- work integrated into `kaori/staging`;
- Staging Integration PASS;
- explicit Local UAT acceptance;
- promotion lineage verified when promoted to `main`;
- Issue/PR evidence recorded.

For work entering the artifact-backed release path, completion additionally requires immutable artifact identity, VPS UAT against that exact artifact, Semantic Versioning release of the accepted digest without rebuilding, production RUN verification, and rollback evidence.

## Developer Check — Draft Development Loop

`KAORI Developer Check` is a separate path-aware workflow for Draft PR development. It is advisory development feedback and is not Admission evidence.

It routes changed paths into the minimum safe focused checks using existing KAORI validation commands. Typical groups include:

- Python -> Ruff format/check, with Pyright where application or validation Python scope requires it;
- Jinja/templates -> djlint;
- frontend/tooling -> existing npm formatting checks;
- migrations/models -> migration graph + focused migration tests;
- domain changes -> focused tests for the affected domain;
- validation-authority or unknown high-risk paths -> fail-safe widened cheap checks.

Representative domain routing includes Vault Management/access, tenant/user/settings, Intelligence, Reports, Kubernetes, Object Storage/storage, Integrations, Platform Operations, and Welcome/shared application surfaces.

Developer Check intentionally excludes production image build, Trivy image scanning, runtime validation, DAST, and unrelated global functional suites. Those remain Full Admission authority.

### Draft

Draft is the implementation loop:

```text
change
  -> Developer Check
  -> review findings
  -> collect all actionable findings
  -> batch repair
  -> Developer Check again
```

Do not mark the PR Ready while Critical/Important review findings or Developer Check failures remain.

### Pre-Ready

**Pre-Ready** is the final cheap gate immediately before Ready. The latest Draft head must have:

- path-aware Developer Check PASS;
- Critical/Important review findings = zero;
- intended implementation complete;
- documentation/contracts already synchronized.

This avoids discovering trivial formatting or focused-contract errors only after the expensive candidate boundary begins.

### Ready / frozen final candidate

When Pre-Ready is clean, mark the PR **Ready for Review** and treat that exact source head as the **frozen final candidate**.

Ready starts governed PR Integration. A new tree/authority normally falls back to **one fresh Full Admission**. An unchanged already-admitted exact tree + authority fingerprint may reuse evidence.

Do not add cleanup, wording, formatting, or opportunistic refactors after freeze. Any source change creates a new candidate identity.

### Full Admission failure return path

A Full Admission failure does not start a one-error/one-rerun loop.

```text
Full Admission FAIL
  -> collect all actionable findings from the run
  -> return to Draft / In Progress
  -> batch repair
  -> Developer Check PASS
  -> Pre-Ready
  -> freeze new Ready candidate
  -> one new Full Admission
```

This **batch repair** rule minimizes expensive validation cycles while preserving the same quality authority.

## Full Admission and Evidence Authority

KAORI uses **Full Admission + exact evidence reuse** with a **validation authority fingerprint**.

The governing rule remains:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

Full Admission preserves authoritative coverage for source linting/formatting, Pyright/type safety, architecture/import/reachability checks, contract and migration tests, functional/integration tests, frontend reproducibility, secrets/SAST/dependency/workflow security, production image build, vulnerability scan, runtime validation, DAST, application assertions, and code-health integrity.

Successful Full Admission publishes immutable evidence containing source commit SHA, source tree SHA, validation profile version, authority fingerprint, run ID/attempt, workflow identity, required gate conclusions, and timestamp.

Validation authority includes `.github/workflows/**`, `.github/ci/**`, `requirements/**`, Admission policy helpers, `scripts/quality_gate.sh`, `scripts/verify_*`, release validation contracts, this delivery workflow authority, Dockerfile, and compose authority.

## Validation Profiles

- **Full Admission** — comprehensive validation for a new tree/fingerprint or forced FALLBACK.
- **PR Integration** — Ready/non-draft evidence lookup before staging merge.
- **Staging Integration** — merge-parent/tree equivalence + exact evidence reuse + fresh Fast Smoke.
- **Promotion** — exact UAT-selected staging lineage verification before `main`.
- **Post-promotion** — resulting `main` lineage verification + fresh Fast Smoke.

Missing, failed, skipped, cancelled, stale, malformed, wrong-tree, or wrong-authority evidence is not reusable. Ambiguity fails closed and produces FALLBACK to Full Admission.

## Human-Readable CI Evidence

Operator-facing output is concise and stable. Result vocabulary is `PASS`, `FAIL`, `SKIP`, `REUSED`, and `FALLBACK`, with visual scanning aids:

- `✅` PASS
- `⚠️` SKIP / REUSED / FALLBACK context
- `❌` FAIL
- `📦` coverage/evidence
- `⏱` duration
- `➡️` next action

Governed job graph names are intentionally short:

```text
Resolve Profile
Static & Governance
Security
Functional Tests
Frontend
Runtime & DAST
Fast Smoke
CI Admission
```

Long Static & Governance execution emits periodic heartbeat output and names the active verifier so a healthy long-running check is distinguishable from a hung runner.

Raw diagnostics remain artifacts. Successful pytest progress dots and repetitive verifier output do not dominate operator logs.

## Representative Examples

### Vault Management feature

```text
Issue
  -> work branch
  -> Draft PR
  -> path-aware Developer Check selects Python + access/security + focused Vault/access tests
  -> batch repair
  -> Pre-Ready PASS
  -> frozen Ready candidate
  -> one Full Admission
  -> staging evidence reuse + Fast Smoke
  -> human UAT
```

### Small issue / burn-down fix

A small issue still follows Issue -> Draft -> Developer Check -> Pre-Ready -> Ready, but its Draft feedback should usually be seconds/minutes rather than a complete production/runtime validation cycle. Full Admission is still required once for the final new candidate; small scope is not a quality bypass.

## Failure Return Paths

- Draft finding -> remain Draft / `Review`; batch repair through Developer Check.
- Ready Full Admission FAIL -> return to Draft / `In Progress`, collect all findings, batch repair, then create a new frozen candidate.
- Staging Integration FAIL -> no UAT progression; repair or FALLBACK.
- Artifact publication or digest-verification FAIL -> do not start VPS UAT.
- Local UAT or VPS UAT FAIL -> return to `In Progress` with UAT evidence.
- Promotion/Post-promotion FAIL -> do not mark delivery complete.
- Release digest mismatch or production RUN FAIL -> do not mark release-bound work Done.
- No failing or unaccepted change is promoted to `main`.

## Staging Integration and UAT

`kaori/staging` is the single integration and Local UAT branch.

Normal staging path:

```text
admitted Ready candidate
  -> merge commit to kaori/staging
  -> Staging Integration
  -> exact evidence reuse + transition lineage
  -> Fast Smoke
  -> CI Admission PASS
  -> Project Status UAT
  -> explicit Local UAT
```

CI is machine verification; Local UAT is human acceptance and must never be fabricated.

## Artifact-Backed VPS and Release Boundary

The artifact-backed path applies when a governed increment is being prepared for VPS UAT and production release under #47–#51. It extends the normal staging authority; it does not replace Developer Check, Full Admission, staging evidence reuse, or Local UAT semantics for ordinary increments.

After an accepted `kaori/staging` SHA passes its required staging gates:

1. Trusted staging automation builds the production target and produces an **immutable OCI image** in the approved configurable Docker Registry.
2. Evidence records the accepted staging SHA, candidate tag, image name, and **OCI digest**. `latest` is never deployment authority.
3. The exact digest is deployed by the production-like Docker Compose stack to the dedicated VPS behind `https://kaori.cloud`.
4. **VPS UAT** explicitly references the deployed staging SHA and OCI digest. Acceptance of a mutable tag without the digest is insufficient.
5. Only the accepted staging lineage may enter the governed `kaori/staging` -> `main` promotion PR; unreviewed source drift invalidates the acceptance pair.
6. The production release uses **Semantic Versioning** and promotes/tags the exact UAT-approved digest **without rebuilding** application bits.
7. Post-promotion integrity, production readiness/health, workers, HTTPS and applicable security checks establish **production RUN** evidence.
8. The previous known-good digest is retained as the rollback target.

The Docker Registry host/repository are configuration rather than provider-specific source assumptions. Registry push credentials and VPS pull credentials remain GitHub/runtime secret authority and must never be committed or copied into Issue/PR bodies.

Release-bound work stays in Project Status `UAT` while artifact publication, VPS UAT, main promotion, or release verification is pending. It reaches `Done` only when the required release/RUN boundary is complete.

## Main Promotion

Accepted increments are promoted through an explicit PR from `kaori/staging` to `main`. Promotion verifies exact accepted staging lineage, evidence identity, and fresh Fast Smoke. After merge, Post-promotion verifies the resulting main lineage.

For artifact-backed releases, the promotion PR also records the UAT-approved OCI digest. Main source promotion and release tagging must not rebuild the accepted application image; the release must reference the same digest accepted during VPS UAT.

The default merge method is **merge commit**. Synchronize `kaori/staging` back to the accepted `main` lineage when required so long-lived branches do not accumulate avoidable drift.

## Hotfix

Urgent production fixes use the same quality boundaries: Draft + Developer Check, Pre-Ready, frozen Ready candidate, Full Admission, applicable UAT, and merge. Expedite sequencing is allowed; validation bypass is not. If a hotfix is released through the artifact-backed path, immutable digest, applicable VPS acceptance, release identity, production RUN, and rollback evidence remain required.

## Label Authority

KAORI retains GitHub's built-in `documentation` label. Custom labels use namespaced `area:*`, `scope:*`, `quality:*`, `impact:*`, and `workflow:*`. Native Issue Type remains type authority; Project fields remain Status/Priority/Sprint authority.

## Branch Hygiene

Merged temporary branches are deleted when no active dependency remains. `main` and `kaori/staging` are the only default long-lived branches. Before deleting a branch, verify all required commits are represented in destination lineage. `kaori/working` must not be deleted until issue #10 confirms no required unique commit would be lost.

## Platform Governance Convergence

When Platform Governance / Platform Workflow standards are formally approved, KAORI converges by gap analysis, terminology mapping, migration planning, replacing duplicated rules, referencing platform authority, and retaining KAORI-specific extensions.
