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
  -> path-aware Developer Check / targeted validation
  -> collect review + Developer Check findings
  -> batch repair
  -> Pre-Ready cheap gate
  -> Ready for Review + frozen final candidate
  -> PR Integration
     -> one Full Admission on the exact frozen candidate when reusable evidence is unavailable
  -> merge commit to kaori/staging
  -> Staging Integration
     -> reuse exact admitted evidence + Fast Smoke when reusable
     -> otherwise FALLBACK to one fresh Full Admission only when evidence/lineage cannot be proven
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

> **Develop cheaply in Draft, run comprehensive validation once on the frozen Ready candidate, then reuse that exact evidence across staging and promotion whenever tree, validation authority, and lineage remain equivalent.**

Draft work-branch validation is intentionally bounded. Full Admission is the frozen final-candidate admission boundary and a fail-closed integration fallback; it is never the normal development/debug loop.

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

A normal work-branch -> `kaori/staging` Pull Request opens as **Draft**. Draft is the implementation/review loop under path-aware Developer Check / targeted validation. After Pre-Ready is clean, changing the PR to **Ready for Review** freezes that exact head and transfers validation authority to PR Integration / Full Admission.

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

### Read-first recovery order

When work resumes after context loss, handoff, tool interruption, or stale conversation memory, recover authority from the repository before making a mutation. The **Read-first recovery order** is:

1. `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`.
2. `docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md`.
3. `docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md`.
4. `.github/PULL_REQUEST_TEMPLATE.md` and relevant `tests/contracts/release/` governance contracts.
5. The governing Issue contract and its current relationships/dependencies.
6. The current work branch / PR exact head SHA and compare against current `kaori/staging`.
7. Current Actions evidence for that exact source SHA.
8. Current `kaori/staging` / `main` lineage and accepted integration evidence.

If remembered guidance conflicts with admitted repository authority, the admitted repository source wins. Do not ask the maintainer to repeat a rule that can be recovered from these sources.

### Repository Metadata Hygiene Gate

Repository metadata is delivery evidence and is checked at every applicable synchronization boundary. Before a candidate is treated as Pre-Ready, before staging integration, and before final completion, audit at minimum:

```text
repo:OXY7O/KAORI is:pr no:label
repo:OXY7O/KAORI is:pr no:assignee
```

Expected result is **0** for governed PRs. Closed, merged, or superseded PRs remain audit evidence and must not be left without applicable labels/assignee merely because they are no longer source authority.

Also verify the governing Issue/PR Project membership, lifecycle Status, Sprint, Native Issue Type, Priority, Story Points, Milestone, relationships, and Development linkage where applicable. Unsupported Project/custom-field mutations must be reported to the maintainer with exact card, field, and intended value; never copy them into a duplicate body table or invent replacement labels.

**Never use Full Admission as the Draft development loop.** Metadata repair, review, and implementation remain under path-aware Developer Check until Pre-Ready; only the frozen Ready candidate enters comprehensive admission.

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

Every `kaori/*` branch except `kaori/staging` is a work branch.

Draft work branches use path-aware Developer Check / targeted validation.

Ready for Review triggers Full Admission on the frozen final candidate.

After merge to `kaori/staging`, exact evidence reuse + Fast Smoke is the normal staging path.

A Pull Request to `main` is a governed promotion only when its source is exactly `kaori/staging`. Direct work-branch-to-main PRs are outside the standard delivery path and must not become a comprehensive-validation bypass.

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

Code complete and automated validation are necessary but not sufficient. Applicable completion requires:

- implementation complete;
- changed-behavior tests pass;
- relevant static, architecture, type, frontend, security, integration, runtime, migration, and DAST authorities pass or are reused only through exact accepted evidence;
- documentation/contracts aligned;
- no known regression unresolved;
- work integrated into `kaori/staging`;
- Staging Integration PASS, either through reusable exact evidence + Fast Smoke or a staging Full Admission fallback;
- explicit Local UAT acceptance;
- promotion lineage verified when promoted to `main`;
- Issue/PR evidence recorded.

For work entering the artifact-backed release path, completion additionally requires immutable artifact identity, VPS UAT against that exact artifact, Semantic Versioning release of the accepted digest without rebuilding, production RUN verification, and rollback evidence.

## Developer Check — Work-Branch Loop

`Developer Check` is the path-aware authority for Pull Requests from every `kaori/*` work branch except `kaori/staging` into `kaori/staging` while the PR remains Draft. It is the implementation and Pre-Ready loop and remains targeted/non-comprehensive.

It routes changed paths into the minimum safe focused checks using existing KAORI validation commands. Typical groups include:

- Python -> Ruff format/check, with Pyright where application or validation Python scope requires it;
- Jinja/templates -> djlint;
- frontend/tooling -> existing npm formatting checks;
- migrations/models -> migration graph + focused migration tests;
- domain changes -> focused tests for the affected domain;
- validation-authority or unknown high-risk paths -> fail-safe widened targeted checks.

Representative domain routing includes Vault Management/access, tenant/user/settings, Intelligence, Reports, Kubernetes, Object Storage/storage, Integrations, Platform Operations, and Welcome/shared application surfaces.

Developer Check intentionally excludes production image build, Trivy image scanning, runtime validation, DAST, and unrelated global functional suites. Those belong to frozen-candidate Full Admission and governed staging/main transition authority.

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

**Pre-Ready** is the final cheap gate immediately before Ready. The latest work-branch head must have:

- path-aware Developer Check PASS;
- Critical/Important review findings = zero;
- intended implementation complete;
- documentation/contracts already synchronized.

This prevents trivial formatting, targeted-contract, or review findings from reaching staging.

### Ready / frozen final candidate

When Pre-Ready is clean, mark the PR **Ready for Review** and treat that exact source head as the frozen work-branch candidate.

Ready enters **PR Integration**. If exact reusable Full Admission evidence does not already exist for that tree + authority fingerprint + profile version, PR Integration fails closed into one fresh Full Admission on the frozen candidate. A successful run publishes immutable evidence for later staging/promotion reuse.

Do not add cleanup, wording, formatting, or opportunistic refactors after freeze. Any source change invalidates the prior final-candidate evidence; substantial repairs should return the PR to Draft, pass Developer Check/Pre-Ready again, then produce a new frozen Ready candidate.

## Full Admission and Evidence Authority

KAORI uses **Full Admission + exact evidence reuse** with a **validation authority fingerprint** across the frozen final-candidate and governed integration transitions.

The governing rule remains:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

A Ready work-branch PR to `kaori/staging` first resolves PR Integration. Without valid exact evidence it executes one fresh Full Admission on the frozen candidate. After merge, a `kaori/staging` push first attempts to reuse that exact immutable evidence; if tree/authority/lineage are valid it runs only fresh Fast Smoke. If evidence is unavailable or invalid, staging fails closed into one fresh Full Admission rather than silently accepting uncertainty.

Full Admission preserves authoritative coverage for source linting/formatting, Pyright/type safety, architecture/import/reachability checks, contract and migration tests, functional/integration tests, frontend reproducibility, secrets/SAST/dependency/workflow security, production image build, vulnerability scan, runtime validation, DAST, application assertions, and code-health integrity.

Successful Full Admission publishes immutable evidence containing source commit SHA, source tree SHA, validation profile version, authority fingerprint, run ID/attempt, workflow identity, required gate conclusions, and timestamp.

Validation authority includes `.github/workflows/**`, `.github/ci/**`, `requirements/**`, Admission policy helpers, `scripts/quality_gate.sh`, `scripts/verify_*`, release validation contracts, this delivery workflow authority, Dockerfile, and compose authority.

### Integration failure return path

A Ready Full Admission or Staging Integration failure does not create a one-error/one-rerun loop:

```text
Admission / Staging Integration FAIL
  -> collect all actionable findings
  -> return to Draft on the governing work branch / issue-linked repair branch
  -> batch repair
  -> Developer Check + Pre-Ready PASS
  -> freeze a new Ready candidate
  -> Full Admission once for the new candidate
  -> merge to kaori/staging
  -> exact evidence reuse + Fast Smoke
```

This batch-repair rule keeps expensive validation out of the development loop while preserving fail-closed candidate and integration authority.

## Validation Profiles

- **Full Admission** — comprehensive validation for the frozen Ready candidate when exact evidence is unavailable, and the fail-closed fallback for a governed transition whose evidence/lineage cannot be proven.
- **PR Integration** — Ready work-branch PR -> `kaori/staging`; exact evidence lookup and normally one Full Admission for the frozen candidate.
- **Staging Integration** — `kaori/staging` push; exact evidence lookup + lineage verification + Fast Smoke when reusable, otherwise Full Admission fallback on staging.
- **Promotion** — `kaori/staging` -> `main` PR; exact UAT-selected staging lineage verification + evidence reuse + Fast Smoke.
- **Post-promotion** — resulting `main` lineage verification + evidence reuse + fresh Fast Smoke.

Missing, failed, skipped, cancelled, stale, malformed, wrong-tree, or wrong-authority evidence is not reusable. Ambiguity fails closed at the staging/main integration authority; it must never redirect comprehensive validation back onto a work branch.

## Human-Readable CI Evidence

Operator-facing output is concise and stable. Result vocabulary is `PASS`, `FAIL`, `SKIP`, `REUSED`, and `FALLBACK`, with visual scanning aids:

- `✅` PASS
- `⚠️` SKIP / REUSED / FALLBACK context
- `❌` FAIL
- `📦` coverage/evidence
- `⏱` duration
- `➡️` next action

Governed integration job graph names are intentionally short:

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

### Telegram delivery notification authority

Telegram delivery notifications are observational only. They do not participate in CI admission, UAT acceptance, promotion authorization, release authorization, or deployment authority.

Trusted-branch delivery notifications must consume **completed** `Full Admission` evidence rather than occupy a `platform-ci` runner while polling for a not-yet-started run. The notification workflow therefore uses the completed `workflow_run` identity and validates the canonical workflow path, trusted repository, source event, source repository, trusted branch, exact source SHA, and completed state before secret-bearing execution.

The scheduled PR-failure observer remains a separate non-authoritative path. Pull-request or fork workflow completion must never inherit the trusted-push Telegram secret boundary.

GitHub sources `workflow_run` listeners from the repository default branch. A change to this listener can be admitted through `kaori/staging` first, but the new event-driven listener becomes the active repository authority only after the same workflow definition reaches `main`. During that staging-only interval, delivery admission remains unaffected; do not reintroduce push-time polling to bridge the activation boundary.

## Representative Examples

### Vault Management feature

```text
Issue
  -> kaori/* work branch
  -> Draft PR to kaori/staging
  -> path-aware Developer Check selects Python + access/security + focused Vault/access tests
  -> batch repair
  -> Pre-Ready PASS
  -> frozen Ready candidate
  -> targeted Developer Check remains authoritative
  -> merge to kaori/staging
  -> staging evidence lookup
     -> Fast Smoke when reusable
     -> Full Admission fallback on staging when required
  -> human UAT
```

### Small issue / burn-down fix

A small issue follows Issue -> work branch -> Draft -> Developer Check -> Pre-Ready -> Ready -> staging merge. Its work-branch feedback should remain seconds/minutes rather than a complete production/runtime validation cycle. If the resulting staging tree lacks reusable admission evidence, the comprehensive suite runs once on `kaori/staging`, not on the work branch.

## Failure Return Paths

- Work-branch Developer Check finding -> remain `In Progress`/`Review`; batch repair through targeted Developer Check.
- Ready work-branch finding -> keep the candidate out of staging until Developer Check/review is green; do not start Full Admission on the work branch.
- Staging Integration / staging Full Admission FAIL -> no UAT progression; repair through an issue-linked work branch, then integrate again.
- Artifact publication or digest-verification FAIL -> do not start VPS UAT.
- Local UAT or VPS UAT FAIL -> return to `In Progress` with UAT evidence.
- Promotion/Post-promotion FAIL -> do not mark delivery complete.
- Release digest mismatch or production RUN FAIL -> do not mark release-bound work Done.
- No failing or unaccepted change is promoted to `main`.

## Staging Integration and UAT

`kaori/staging` is the single integration, comprehensive-validation fallback, and Local UAT authority.

Normal staging path:

```text
targeted-green frozen work-branch candidate
  -> merge commit to kaori/staging
  -> Staging Integration
  -> exact evidence lookup + transition lineage
     -> reusable: Fast Smoke
     -> unavailable/invalid: Full Admission on kaori/staging
  -> CI Admission PASS
  -> Project Status UAT
  -> explicit Local UAT
```

CI is machine verification; Local UAT is human acceptance and must never be fabricated.

## Artifact-Backed VPS and Release Boundary

The artifact-backed path applies when a governed increment is being prepared for VPS UAT and production release under #47–#51. It extends the normal staging authority; it does not replace Developer Check, staging validation/evidence reuse, or Local UAT semantics for ordinary increments.

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

Accepted increments are promoted through an explicit PR from `kaori/staging` to `main`. `Full Admission` accepts a PR to `main` as a governed promotion only when its head is exactly `kaori/staging`. Promotion verifies exact accepted staging lineage, reuses admitted evidence, and runs fresh Fast Smoke. After merge, Post-promotion verifies the resulting main lineage with the same evidence-reuse principle.

For artifact-backed releases, the promotion PR also records the UAT-approved OCI digest. Main source promotion and release tagging must not rebuild the accepted application image; the release must reference the same digest accepted during VPS UAT.

The default merge method is **merge commit**. Synchronize `kaori/staging` back to the accepted `main` lineage when required so long-lived branches do not accumulate avoidable drift.

## Hotfix

Urgent production fixes use the same quality boundaries: issue-linked `kaori/*` work branch, targeted Developer Check, Pre-Ready, frozen Ready candidate Full Admission, staging evidence reuse/Fast Smoke, applicable UAT, and governed promotion. Expedite sequencing is allowed; validation bypass is not. Full Admission must not become a mutable hotfix development loop. If a hotfix is released through the artifact-backed path, immutable digest, applicable VPS acceptance, release identity, production RUN, and rollback evidence remain required.

## Label Authority

KAORI retains GitHub's built-in `documentation` label. Custom labels use namespaced `area:*`, `scope:*`, `quality:*`, `impact:*`, and `workflow:*`. Native Issue Type remains type authority; Project fields remain Status/Priority/Sprint authority.

## Branch Hygiene

Merged temporary branches are deleted when no active dependency remains. `main` and `kaori/staging` are the only default long-lived branches. Before deleting a branch, verify all required commits are represented in destination lineage. `kaori/working` must not be deleted until issue #10 confirms no required unique commit would be lost.

## Platform Governance Convergence

When Platform Governance / Platform Workflow standards are formally approved, KAORI converges by gap analysis, terminology mapping, migration planning, replacing duplicated rules, referencing platform authority, and retaining KAORI-specific extensions.
