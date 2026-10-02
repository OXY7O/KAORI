# KAORI Application Delivery Workflow

**Governance Version:** 2.2  
**Scope:** KAORI application repository  
**Authority:** Application-local baseline  
**Future Authority:** Platform Governance / Platform Workflow standards when formally adopted

## Lifecycle

KAORI Engineering Evolution v2 supports two first-class development feedback tracks. They differ only before **Candidate Freeze** and converge on the same governed admission and acceptance path.

```text
Idea / Request
  -> Issue
  -> Backlog / Refinement
  -> Ready
  -> issue-linked work branch from kaori/staging
       |
       +-> Local-First / Dev Container
       |     -> implementation + local iteration
       |     -> shared Developer Validation Plan
       |     -> existing targeted validators/tests
       |     -> human local review + batch repair
       |     -> Local Candidate accepted
       |
       +-> GitHub-First
             -> Draft PR to kaori/staging
             -> shared path/capability-aware Developer Check
             -> collect review + Developer Check findings
             -> batch repair
             -> Pre-Ready cheap gate
             -> Ready for Review
       |
       +--------------------+
                            |
                       Candidate Freeze
                            |
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

> **Develop cheaply in the track that fits the work, freeze one candidate, verify that exact head once, pay Full Admission once, then reuse immutable evidence through staging and promotion when lineage remains valid.**

**Local-First** is preferred when large features, broad UI/UX iteration, provider workflows, or substantial refactoring would otherwise turn GitHub CI into an interactive development environment. The canonical VS Code Dev Container provides the runtime for implementation, local human review, and the shared Developer Validation Plan.

**GitHub-First** remains the efficient default for bounded fixes, documentation changes, small backend/frontend changes, and other work where Draft PR feedback is already proportional to the scope.

The two tracks never create separate acceptance standards. Candidate Freeze is the convergence boundary. Any source change after freeze invalidates the frozen candidate and returns the work to the appropriate development track.

Draft work-branch validation remains intentionally bounded. Ready is still the governed final-candidate boundary: Full Admission runs once on the exact frozen head, while later staging/promotion transitions reuse that immutable evidence when lineage remains valid.

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

KAORI uses the Pull Request state according to the selected development track while preserving one downstream authority.

**GitHub-First:** open the normal work-branch -> `kaori/staging` Pull Request as **Draft**. Draft is the implementation/review loop and remains under the shared capability-aware Developer Check. Changing the PR to Ready freezes the candidate, reruns Developer Check on that exact head, and invokes comprehensive Full Admission only after the Developer Check aggregate passes.

**Local-First:** keep implementation/review on the issue-linked work branch and canonical Dev Container until the Local Candidate is accepted. At Candidate Freeze, open the work-branch -> `kaori/staging` Pull Request **Ready for Review** on that exact frozen head. The opened Ready PR runs the authoritative exact-head Developer Check once and proceeds to Full Admission only if that aggregate passes. Opening a Draft PR earlier is allowed when GitHub collaboration is useful, but doing so intentionally selects the GitHub-First feedback loop.

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

Work branches use the shared Developer Validation Plan in either Local-First or GitHub-First feedback. GitHub-First Draft PRs run path/capability-aware Developer Check during iteration; Local-First branches run the same planning authority in Dev Container before Candidate Freeze. The frozen candidate may enter Full Admission only after the authoritative exact-head Developer Check aggregate passes.

Comprehensive validation authority begins at the Ready/frozen-candidate boundary and is then reused through `kaori/staging` and `main` when exact evidence and lineage remain valid.

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

`Developer Check` remains the authoritative exact-head verification for Pull Requests from every `kaori/*` work branch except `kaori/staging` into `kaori/staging`. Engineering Evolution v2 separates **development feedback** from **candidate verification** without changing Full Admission authority.

The repository-owned `scripts/resolve_developer_check_plan.py` is the single routing authority. It resolves the source diff into Python, template, frontend, migration, report, contract, capability, and focused-test requirements. GitHub Actions and the Dev Container consume the same planner; they must not maintain competing path-routing matrices.

The planner prefers the narrowest existing capability test boundary. For example:

```text
app/kubernetes/tenant/*
  -> tests/kubernetes/tenant

app/kubernetes/inventory/*
  -> tests/kubernetes/inventory

app/integrations/runtime/*
  -> tests/integrations/runtime
```

When a nested authoritative boundary does not exist, routing falls back to the parent domain. Shared, unknown, persistence, and validation-authority changes widen or fall back conservatively. Changes to CI/delivery authority run release-contract + migration coverage during Developer Check; comprehensive repository coverage remains owned by Full Admission.

Existing validation commands remain authoritative. The planner selects them; it does not replace Ruff, DjLint, Pyright, migration verification, frontend validation, pytest, or other admitted checks.

### Local-First / Dev Container

Local-First is the preferred development feedback loop for large features, UI/UX iteration, provider/infrastructure workflows, and substantial refactors.

```text
change
  -> Dev Container
  -> Developer Validation Plan
  -> selected existing checks
  -> human local review
  -> collect all actionable findings
  -> batch repair
  -> repeat locally
  -> Local Candidate accepted
  -> Candidate Freeze
  -> Ready PR
  -> exact-head Developer Check
```

Resolve the same plan used by GitHub after synchronizing the staging reference:

```bash
git fetch origin kaori/staging
python scripts/resolve_developer_check_plan.py \
  --base-ref origin/kaori/staging \
  --head-ref HEAD
```

Local validation is development evidence, not a substitute for GitHub admission evidence.

### GitHub-First Draft

GitHub-First preserves the existing Draft implementation loop for bounded work:

```text
change
  -> Draft PR
  -> Developer Check
  -> review findings
  -> collect all actionable findings
  -> batch repair
  -> Developer Check again
```

Do not mark the PR Ready while Critical/Important review findings or Developer Check failures remain.

### Pre-Ready

**Pre-Ready** is the final cheap gate immediately before Ready in the GitHub-First track. The latest work-branch head must have:

- capability-aware Developer Check PASS;
- Critical/Important review findings = zero;
- intended implementation complete;
- documentation/contracts already synchronized.

Local-First performs the equivalent boundary through explicit Local Candidate acceptance before Candidate Freeze.

### Candidate Freeze / Ready

Candidate Freeze is the single convergence boundary for both development tracks.

After freeze:

- the exact source head is immutable for admission;
- authoritative Developer Check runs on that exact head;
- Full Admission may start only after Developer Check PASS;
- any source change invalidates the candidate and returns work to Local-First or GitHub-First feedback;
- no track may bypass Full Admission, staging integration, applicable UAT, promotion, or release evidence.

For GitHub-First, marking a Draft PR **Ready for Review** declares Candidate Freeze. For Local-First, opening the accepted work branch as a **Ready for Review** PR declares Candidate Freeze.

## Full Admission and Evidence Authority

KAORI uses **Full Admission + exact evidence reuse** with a **validation authority fingerprint** beginning at the frozen Ready candidate and continuing through governed integration branches.

The governing rule remains:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

A Ready feature PR first attempts exact evidence reuse for its exact head. A new frozen candidate without reusable evidence fails closed into one fresh Full Admission. After merge, a `kaori/staging` push reuses that exact evidence and runs fresh Fast Smoke when transition lineage is valid. If staging cannot prove reusable evidence/lineage, it fails closed into one fresh Full Admission on `kaori/staging` rather than silently passing.

Full Admission preserves authoritative coverage for source linting/formatting, Pyright/type safety, architecture/import/reachability checks, contract and migration tests, functional/integration tests, frontend reproducibility, secrets/SAST/dependency/workflow security, production image build, vulnerability scan, runtime validation, DAST, application assertions, and code-health integrity.

The comprehensive gate set runs as one native GitHub Actions matrix with `fail-fast: true` and a current host ceiling of `max-parallel: 2`. Static & Governance, Security, Functional Tests, Frontend, and Runtime & DAST remain distinct matrix children. If any child fails, GitHub cancels queued/in-progress sibling matrix work instead of consuming the remaining comprehensive critical path. Cancellation cleanup remains mandatory for Compose/runtime resources.

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

### Large Local-First feature

```text
Issue
  -> issue-linked work branch
  -> Dev Container implementation
  -> shared Developer Validation Plan
  -> targeted existing checks
  -> human local review
  -> batch repair
  -> Local Candidate accepted
  -> Candidate Freeze
  -> Ready PR to kaori/staging
  -> exact-head Developer Check PASS
  -> one Full Admission on the frozen head
  -> merge to kaori/staging
  -> evidence lookup + Fast Smoke
  -> human UAT
```

This is the preferred shape when repeated GitHub runs would otherwise become the interactive development loop.

### Vault Management feature

A bounded feature may still use GitHub-First when its feedback remains proportional:

```text
Issue
  -> kaori/* work branch
  -> Draft PR to kaori/staging
  -> shared Developer Validation Plan selects Python + access/security + focused Vault/access tests
  -> batch repair
  -> Pre-Ready PASS
  -> Candidate Freeze / Ready for Review
  -> exact-head Developer Check PASS
  -> one Full Admission on the frozen Ready head
  -> merge to kaori/staging
  -> staging evidence lookup + lineage verification
     -> Fast Smoke when reusable
     -> Full Admission fallback on staging only when required
  -> human UAT
```

### Small issue / burn-down fix

A small issue normally follows the GitHub-First path: Issue -> work branch -> Draft -> Developer Check -> Pre-Ready -> Candidate Freeze / Ready -> exact-head Developer Check -> Full Admission -> staging merge. Draft feedback should remain seconds/minutes.

If a nominally small fix expands unexpectedly, it may switch to Local-First without changing the downstream authority.

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
