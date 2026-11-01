# KAORI Application Delivery Workflow

**Governance Version:** 2.2  
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
  -> choose one inner development track
     -> Local-First / Dev Container
        -> implement + local review
        -> shared Developer Check plan + targeted local validation
        -> collect findings + batch repair
     -> OR GitHub-First
        -> Draft PR to kaori/staging
        -> path-aware Developer Check / targeted validation
        -> collect review + Developer Check findings
        -> batch repair
  -> converge on one candidate
     -> Draft PR to kaori/staging exists
     -> path-aware Developer Check PASS
     -> Pre-Ready cheap gate
  -> Ready for Review + frozen final candidate
  -> exact-head Developer Check PASS
  -> one governed Full Admission on the exact frozen head
     -> exact evidence reuse when already admitted
     -> otherwise comprehensive gates run in parallel
  -> merge commit to kaori/staging
  -> Staging Integration
     -> reuse exact admitted evidence + Fast Smoke
     -> FALLBACK to fresh Full Admission only when evidence/lineage cannot be proven
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

> **Develop cheaply in the context-appropriate Local-First or GitHub-First loop, converge on one targeted-green candidate, freeze it at Ready, pay Full Admission once for that exact candidate, then reuse immutable evidence through staging and promotion when lineage remains valid.**

Draft work-branch validation is intentionally bounded. Ready is the governed final-candidate boundary: Full Admission runs once on the exact frozen head, while later staging/promotion transitions reuse that immutable evidence when lineage remains valid.

### Engineering Evolution v2 development tracks

The two tracks are development-feedback choices, not separate delivery outcomes.

**Local-First / Dev Container** is appropriate when feature breadth, visual iteration, provider/infrastructure behavior, or refactoring would make repeated CI round-trips the dominant feedback cost. Local work uses the canonical Dev Container and the repository-owned `scripts/developer_check_plan.py` authority to resolve the same changed-path validation plan consumed by GitHub Actions.

**GitHub-First** remains appropriate for bounded fixes, documentation, small refactors, and narrow changes where Draft PR Developer Check is already the cheapest useful loop.

Both tracks converge before Ready. A Local-First change must still have a governed Draft PR, pass the authoritative exact-head Developer Check, freeze the final candidate, pass Full Admission, integrate through `kaori/staging`, receive applicable UAT, and follow the same promotion/release rules. Local evidence accelerates development; it never substitutes for repository admission evidence.

A separate linked Git worktree is supported for local Dev Container validation of
an immutable candidate while preserving another checkout's staged/uncommitted
changes. Source Hygiene recognizes Git checkouts with either a `.git` directory
(normal checkout) or a `.git` metadata pointer file (linked worktree) and
checks **tracked** source with `git ls-files`. Ignored Ruff caches and retained
`tmp/ci-artifacts` diagnostics are allowed only as local tooling output, not
in a tracked source tree or unpacked source archive. The latter is deliberately
checked in archive mode with all files visible (CI hygiene issue #4156).


Developer Check planning follows **capability impact with fail-safe widening**. A known capability may select its owning tests and explicit dependent contracts. Shared, CI, release-authority, migration, or uncertain changes widen validation rather than assuming isolation. Full Admission remains comprehensive at the frozen-candidate boundary.


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

A normal work-branch -> `kaori/staging` Pull Request opens as **Draft**. Draft is the implementation/review loop and remains under path-aware Developer Check / targeted validation only. Changing the PR to Ready freezes the candidate and requires an **independently verified exact-head Developer Check PASS** before any comprehensive Full Admission. When a fresh, successful Draft run has an auditable route artifact matching the live trusted PR, exact head/base SHA, source tree, validation authority, toolchain, and every required GitHub job conclusion, the Ready aggregate may reuse those already-proven focused results. All missing, stale, failed, cancelled, unknown, or altered evidence falls back to a **fresh Ready Developer Check**, not an assumed PASS. The Ready aggregate remains required and Full Admission is always comprehensive on a new frozen candidate. The independent **Ready Admission Guard** additionally requires actual Full Admission SUCCESS, so GitHub's native green workflow status cannot conceal a skipped mandatory Full Admission job after optimized lane reuse.

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

**Never use Full Admission as the development/debug loop.** Draft implementation, metadata repair, and review remain under path-aware Developer Check; only the exact frozen Ready candidate may enter governed Full Admission.

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

Every `kaori/*` branch except `kaori/staging` is a work branch.

Work branches use path-aware Developer Check / targeted validation while Draft and on the exact Ready head. The frozen Ready candidate may enter Full Admission only after that exact-head Developer Check aggregate passes.

Comprehensive validation authority begins at the Ready/frozen-candidate boundary and is then reused through `kaori/staging` and `main` when exact evidence and lineage remain valid.

A Pull Request to `main` is a governed promotion only when its source is exactly `kaori/staging`. Direct work-branch-to-main PRs are outside the standard delivery path and must not become a comprehensive-validation bypass.

`kaori/working` is retired only after issue #10 proves all required commits are represented in `kaori/staging`.


### Temporary DevContainer review workbench (#2227)

The existing `kaori/review/staging-uat` branch is an explicitly governed **temporary, non-release workbench** for combining issue-owned changes and collecting exploratory DevContainer UAT evidence. It is **not** a third official long-lived integration, release, or promotion authority: `kaori/staging` remains the only source of comprehensive admission and staging integration; `main` remains the governed production lineage. Workbench acceptance never substitutes for Ready Developer Check, all five Full Admission lanes, CI Admission, Security/DAST, staging Fast Smoke, immutable release evidence, or human acceptance of the deployed candidate.

- **Separate workstream ownership:** UAT review PRs retain their own issue/branch and target `kaori/review/staging-uat` only while on hold. An approved workbench merge is not approval to promote its full tree. Independent CI, operations and performance fixes still flow through normal issue-scoped PRs to `kaori/staging`.
- **One-way synchronization:** after an accepted staging change, inspect both refs, commit ancestry and open review-target PRs before syncing **staging → review**. If review has no unique commits, use fast-forward with `force=false` and a verified expected head; if diverged, use an explicit reviewed merge commit into review instead. Never reset/force-push/rebase a shared review branch, alter pending PR heads, or reverse-sync unaccepted review commits to staging.
- **Later promotion:** reconcile only the specifically reviewed and human-accepted issue scope on a branch from *current* `kaori/staging`, then use ordinary Draft → Ready → Full Admission → staging integration. Never use the temporary review branch as a staging-to-main promotion shortcut.
- **Evidence boundary:** for each exploratory DevContainer session record exact checkout SHA, environment, configured provider/instance identity, scenario, runner/tester, actual positive/negative results and screenshots/traces where captured, and explicit human decision. When an external Kubernetes provider, RBAC, migration, hosted ingress, TLS, deployment, recovery or real infrastructure evidence is unavailable, mark that scenario **NOT RUN** or **BLOCKED**, not PASS. The DevContainer is not a stand-in for the production-like UAT host.

**Dated accepted-source admission (#1710, initial 2026-10-26; reconfirmed 2026-11-01).** The maintainer initially accepted the committed DevContainer snapshot `kaori/review/staging-uat@1a9a708f044e06d584f1882e83877812dcfbac88` on 2026-10-26. On 2026-11-01, the maintainer explicitly confirmed that the **latest reviewed/approved source is the committed review workbench**, while directing its admission through existing gates rather than replacing them. [Workbench reconciliation #4161](https://github.com/OXY7O/KAORI/pull/4161) merged the issue-owned corrections and reviewed workbench history; subsequent issue-scoped review PRs #4162, #4163, #4164, #4165, #4167 and #4169 integrated Ruff, DjLint, DevContainer preflight and test-contract corrections into `kaori/review/staging-uat@79ee563edd6ac304da183c417edd11d3dcc32c75`. This later **exact SHA**, not the moving branch name, is the additional accepted source boundary for this one admission. The independent issue #1710 work branch `kaori/task-1710-reviewed-staging-admission-20261026` was advanced **non-forced** from its ancestor `2064c2e7d2c316b466d19e5bbe90b96faa2bd094` to `79ee563edd6ac304da183c417edd11d3dcc32c75` (177 ahead, zero behind across the two non-forced sync checkpoints), retaining prior corrective history and its separate PR #3399 to `kaori/staging`.

The 15 PR heads still open against the review workbench at the 2026-11-01 checkpoint remain **excluded/unmerged**; only commits already integrated into the explicitly accepted SHA are admitted. This operator-approved **dated source-reconciliation exception** does not authorize routine review-to-staging synchronization, future workbench commits, bypass of issue-owned remediation, or any replacement of the standard two-branch lifecycle. Each new corrective commit invalidates previous exact-head CI evidence and must undergo Draft Developer Check, recorded Pre-Ready decision, frozen Ready Developer Check and Full Admission, staging verification, immutable RC/digest, governed hosted UAT and independent human server acceptance. Never treat source inspection, DevContainer UAT or a merged workbench PR as those proofs.

This exception remains under #2227 until an explicit documented review retires it; it does not replace the canonical two-branch delivery workflow. Current review branch and pending PR inventory must be rechecked at execution time instead of relying on historical head SHAs or PR counts.

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

## New/Changed Capability — Mandatory Gate Evidence

Each added or materially changed KAORI domain, capability, provider, feature, operator-facing workspace or static verifier must comply with the **existing** `docs/engineering/TERMINAL_OUTPUT.md` evidence contract and `docs/architecture/RELEASE_SURFACE_COVERAGE.md` ownership/change-control requirements before the change can be accepted. This applies equally to Source Control/GitHub, Secrets Management/Vault, Kubernetes, Artifact Registry, Analytics, Intelligence and future integrations; never create provider-named top-level products solely to display coverage.

In the governing Issue and PR, identify the domain-first release owner, scoped purpose, applicable navigation/Blueprint/taxonomy changes, the canonical command or actual test selection, security/negative testing and executed evidence paths. In CI, show the executed check's purpose, actual result, duration and diagnostics through the existing steps, Summary and artifacts. A new independent verifier needs a specific purpose label; an existing verifier can cover the new capability when that contract is genuinely sufficient. Do not introduce duplicated tests solely for presentation.

**Admission boundaries:** `REGISTERED` indicates ownership only; test PASS requires executed evidence, and green static/functional checks do not substitute for Security, Runtime/DAST, deployment and explicit human acceptance when applicable. SKIP, REUSED, NOT RUN and BLOCKED must remain honest. Reviewers must reject a new capability whose ownership, purpose or required evidence cannot be identified. The approved validation gates and the Issue → Branch → PR → staging → UAT → promotion flow remain authoritative and unchanged.

## Developer Check — Work-Branch Loop

`Developer Check` is the path-aware authority for Pull Requests from every `kaori/*` work branch except `kaori/staging` into `kaori/staging`. Draft runs provide the cheap development loop; Ready/synchronize events rerun the same targeted authority on the exact current head before any Full Admission may start.

It routes changed paths once into the minimum safe focused checks using existing KAORI validation commands. Selected checks then execute in independent Draft lanes where safe:

- **Python & Governance** -> workflow lint when widened, Ruff format/check, code-health, Pyright/type safety, migration graph, and report verification when selected;
- **Frontend & Focused Validation** -> djlint, existing npm/frontend checks, and only the routed domain/contract/migration pytest paths when selected.

Redundant parent/child focused-test selections are normalized before execution. The final `Developer Check` aggregate fails closed if any required selected lane fails, is cancelled, or is unexpectedly skipped. Unselected lanes may skip without weakening the aggregate.

Representative domain routing includes Vault Management/access, tenant/user/settings, Intelligence, Reports, Kubernetes, Object Storage/storage, Integrations, Platform Operations, and Welcome/shared application surfaces.

Developer Check intentionally excludes production image build, Trivy image scanning, runtime validation, DAST, and unrelated global functional suites. Those remain staging/main integration authority.

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

Ready triggers an exact-head Developer Check authority first: a new execution of the selected lanes **or** a fresh, verified, immutable same-head/base Draft result proven against the live PR, workflow, validation plan, toolchain and successful required GitHub job conclusions. The Ready aggregate must pass independently; any unverifiable evidence invokes the original fresh lanes, and failed/cancelled work never becomes reusable. Only after a successful Ready aggregate does the Developer Check workflow invoke mandatory comprehensive Full Admission for that frozen candidate. Do not add cleanup, wording, formatting, or opportunistic refactors after freeze; any source/base/authority change invalidates the earlier Draft evidence and requires fresh checks.

## Full Admission and Evidence Authority

KAORI uses **Full Admission + exact evidence reuse** with a **validation authority fingerprint** beginning at the frozen Ready candidate and continuing through governed integration branches.

The governing rule remains:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

A Ready feature PR first attempts exact evidence reuse for its exact head. A new frozen candidate without reusable evidence fails closed into one fresh Full Admission. After merge, a `kaori/staging` push reuses that exact evidence and runs fresh Fast Smoke when transition lineage is valid. If staging cannot prove reusable evidence/lineage, it fails closed into one fresh Full Admission on `kaori/staging` rather than silently passing.

Full Admission preserves authoritative coverage for source linting/formatting, Pyright/type safety, architecture/import/reachability checks, contract and migration tests, functional/integration tests, frontend reproducibility, secrets/SAST/dependency/workflow security, production image build, vulnerability scan, runtime validation, DAST, application assertions, and code-health integrity.

The comprehensive gate set runs as one native GitHub Actions matrix with `fail-fast: true` and **temporary `max-parallel: 1`** for the capacity-constrained 8-GB shared builder (#2219). Static & Governance, Security, Functional Tests, Frontend, and Runtime & DAST remain five distinct **required** matrix children; they run **sequentially within a Full Admission** until measured RAM headroom or runner host separation justifies restoring parallelism through a separately reviewed change. If any child fails, GitHub cancels remaining queued siblings; cancellation cleanup remains mandatory for Compose/runtime resources. CI Admission still fails closed unless every required child passes. A single matrix slot does not serialize other workflows on the same physical host; operational runner scheduling must avoid unrelated memory-heavy workloads. This is a temporary resource mitigation, not a reduction in required quality/security/DAST coverage or immutable evidence provenance. Restore `max-parallel: 2` only after an approved capacity upgrade and repeated representative OOM-free Full Admission evidence.

Release-test ownership is non-overlapping. Static & Governance owns Contract/Migration pytest execution; Functional Tests owns the remaining release taxonomy plus explicit E2E. Their JUnit artifacts are recombined by CI Admission into one complete taxonomy evidence surface before reusable Full Admission evidence is published.

Transient JUnit handoff artifacts are keyed to the workflow run rather than `github.run_attempt`. This allows GitHub Actions **Re-run failed jobs** to retain JUnit evidence from matrix children that already succeeded while a newly successful rerun child replaces only its own transient handoff artifact. CI Admission still requires complete matrix success before publishing reusable PASS evidence, and the final evidence keeps run-attempt identity.

Successful Full Admission publishes immutable evidence containing source commit SHA, source tree SHA, validation profile version, authority fingerprint, run ID/attempt, workflow identity, required gate conclusions, and timestamp. Matrix aggregate success attests that every required comprehensive child succeeded; failed/cancelled matrices cannot publish reusable PASS evidence.

Validation authority includes `.github/workflows/**`, `.github/ci/**`, `requirements/**`, Admission policy helpers, `scripts/quality_gate.sh`, `scripts/verify_*`, release validation contracts, this delivery workflow authority, Dockerfile, and compose authority.

### Integration failure return path

A staging Full Admission or Fast Smoke failure does not create a one-error/one-rerun loop:

```text
Staging Integration FAIL
  -> collect all actionable findings
  -> repair on the governing work branch / issue-linked repair branch
  -> Developer Check PASS
  -> merge corrected candidate to kaori/staging
  -> staging evidence lookup
  -> reuse + Fast Smoke, or one Full Admission fallback
```

This batch-repair rule keeps expensive validation out of the development loop while preserving fail-closed integration authority.

## Validation Profiles

- **Full Admission** — comprehensive validation for the exact frozen Ready candidate, or a governed integration fallback when exact evidence cannot be reused.
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
  -> exact-head Developer Check PASS
  -> one Full Admission on the frozen Ready head
  -> merge to kaori/staging
  -> staging evidence lookup + lineage verification
     -> Fast Smoke when reusable
     -> Full Admission fallback on staging only when required
  -> human UAT
```

### Small issue / burn-down fix

A small issue follows Issue -> work branch -> Draft -> Developer Check -> Pre-Ready -> Ready -> exact-head Developer Check -> Full Admission -> staging merge. Draft feedback should remain seconds/minutes. The comprehensive suite runs once for the frozen Ready candidate; staging normally reuses that evidence and runs only Fast Smoke.

## Failure Return Paths

- Work-branch Developer Check finding -> remain `In Progress`/`Review`; batch repair through targeted Developer Check.
- Ready Full Admission finding -> return the PR to Draft, collect all actionable findings, batch repair through Developer Check, then freeze a new Ready candidate.
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
targeted-green Draft candidate
  -> Ready/frozen head
  -> exact-head Developer Check PASS
  -> Full Admission PASS on exact candidate
  -> merge commit to kaori/staging
  -> Staging Integration
  -> exact evidence lookup + transition lineage
     -> reusable: Fast Smoke
     -> unavailable/invalid: Full Admission fallback on kaori/staging
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

Urgent production fixes use the same quality boundaries: issue-linked `kaori/*` work branch, targeted Developer Check, Pre-Ready, frozen Ready candidate, one Full Admission, staging evidence reuse, applicable UAT, and governed promotion. Expedite sequencing is allowed; validation bypass is not. If a hotfix is released through the artifact-backed path, immutable digest, applicable VPS acceptance, release identity, production RUN, and rollback evidence remain required.

## Label Authority

KAORI retains GitHub's built-in `documentation` label. Custom labels use namespaced `area:*`, `scope:*`, `quality:*`, `impact:*`, and `workflow:*`. Native Issue Type remains type authority; Project fields remain Status/Priority/Sprint authority.

## Branch Hygiene

Merged temporary branches are deleted when no active dependency remains. `main` and `kaori/staging` are the only default long-lived branches. Before deleting a branch, verify all required commits are represented in destination lineage. `kaori/working` must not be deleted until issue #10 confirms no required unique commit would be lost.

## Platform Governance Convergence

When Platform Governance / Platform Workflow standards are formally approved, KAORI converges by gap analysis, terminology mapping, migration planning, replacing duplicated rules, referencing platform authority, and retaining KAORI-specific extensions.
