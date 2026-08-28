# KAORI Application Delivery Workflow

**Governance Version:** 1.0  
**Scope:** KAORI application repository  
**Authority:** Application-local baseline  
**Future Authority:** Platform Governance / Platform Workflow standards when formally adopted

## Lifecycle

```text
Idea / Request
  -> Issue
  -> Backlog / Refinement
  -> Ready
  -> issue-linked work branch
  -> full branch CI
  -> Review
  -> kaori/staging integration
  -> full staging CI
  -> UAT
  -> explicit Local UAT acceptance
  -> Done
  -> PR kaori/staging -> main when release/promotion is approved
  -> merge commit
  -> main
```

KAORI uses a closed-loop delivery model. Product ideas, operational findings, defects, technical debt, monitoring signals, and user feedback return to the backlog as governed work items.

## Human-Readable GitHub Standard

GitHub history is a long-lived engineering record. Titles, branches, commits, Pull Requests, comments, and CI evidence must be readable without reconstructing intent from source code.

### Issue titles

Native GitHub Issue Type is the type authority. Once native Issue Types are configured, do not repeat the type in the title.

Preferred:

```text
Self-hosted runner stops accepting sequential CI jobs
Restore canonical static-quality baseline
Publish KAORI delivery workflow and repository templates
```

Avoid:

```text
[BUG] Self-hosted runner stops accepting sequential CI jobs
[TASK] Restore canonical static-quality baseline
fix stuff
misc cleanup
```

Use sentence case, describe one outcome/problem, and omit a trailing period.

### Issue body

Every work item should make the following understandable to a reviewer:

1. Context / problem / outcome.
2. In scope and explicitly out of scope.
3. Testable acceptance criteria.
4. Dependencies and relationships.
5. Security, data, migration, observability, and operational impact where applicable.
6. Verification and UAT requirements.

Chronological execution evidence belongs in Issue comments. Do not repeatedly rewrite historical CI failures in the Issue body; keep the body as the current contract and use comments as the audit timeline.

### Branch names

Normal governed work uses issue-linked temporary branches from the current `kaori/staging` baseline:

```text
kaori/story-<issue>-<slug>
kaori/bug-<issue>-<slug>
kaori/task-<issue>-<slug>
kaori/spike-<issue>-<slug>
kaori/chore-<issue>-<slug>
kaori/tech-debt-<issue>-<slug>
kaori/hotfix-<issue>-<slug>
```

Use lowercase kebab-case for the slug. Do not create a second branch merely to make GitHub's Development sidebar non-empty.

### Commit messages

KAORI uses Conventional Commit syntax with the governed Issue reference at the end:

```text
<type>(<scope>): <imperative summary> #<issue>
```

Examples:

```text
fix(ci): bound tool download retries #15
test(reports): align Analytics Overview publication contract #12
docs(governance): clarify label authority #8
refactor(reports): isolate workbook validation #13
```

Rules:

- one logical change per commit;
- lowercase Conventional Commit type and scope;
- imperative, concrete summary;
- no trailing period;
- include the controlling Issue number;
- do not use vague subjects such as `fix`, `update`, `cleanup`, or `changes` without the affected behavior.

### Pull Request titles

Use the same Conventional Commit subject style, without duplicating the Issue number when the PR body already links it:

```text
fix(ci): bound tool downloads
docs(governance): standardize repository workflow
```

PR titles describe the change; the body owns traceability and evidence.

### Issue linkage in Pull Requests

Use:

```text
Refs #<issue>
```

while work is still moving through staging/UAT.

Use a closing keyword such as:

```text
Closes #<issue>
```

only on the final PR whose successful merge is intended to close the work item. Do not close an Issue merely because an implementation branch or validation PR exists.

### Evidence comments

Technical comments should follow a predictable reading order:

```text
## <Evidence / Investigation / Validation> — YYYY-MM-DD

### Context
What was being validated and on which SHA/run.

### Result
What passed or failed.

### Evidence
Exact run/job/SHA and the actionable finding.

### Decision / Next Step
What changes, what does not change, and why.
```

Keep raw log dumps in GitHub Actions. Issue comments should retain the evidence needed for a human to understand the decision without reading thousands of log lines.

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

`kaori/working` is retired only after issue #10 proves all required commits are represented in `kaori/staging`. Temporary work and validation branches are deleted after integration when no active dependency remains. Issues, PRs, commits, Actions runs, releases, and governance records are the durable audit trail; stale branches are not retained for audit purposes.

## Work Hierarchy

Canonical hierarchy:

```text
Epic
  -> User Story
     -> Task / Bug
```

Spikes may attach to an Epic or Story to resolve uncertainty. Chores and Technical Debt may stand alone when appropriate or attach to a larger outcome. Native GitHub parent/sub-issue relationships are preferred when available.

## Project Status Model

GitHub Project `Status` is the single lifecycle authority:

1. `Inbox` — captured but not yet triaged.
2. `Backlog` — accepted for consideration/refinement, not yet admitted to delivery.
3. `Ready` — Definition of Ready satisfied and eligible for implementation.
4. `In Progress` — implementation or active remediation is underway.
5. `Review` — implementation is complete enough for CI/review/integration assessment.
6. `UAT` — integrated staging evidence is ready for explicit Local UAT.
7. `Done` — Local UAT is explicitly accepted and the work item satisfies Definition of Done.

`workflow:blocked` is exception metadata, not a competing lifecycle Status. A blocked item remains at the lifecycle stage where it is blocked and carries blocker evidence in the Issue.

Refinement is a Backlog activity rather than a separate Status. Staging is an integration authority/branch rather than a separate Status. CI and code review are Review activities rather than separate statuses.

## Sprint and Release

The default Sprint cadence is two weeks and remains flexible.

- GitHub Project **Iteration** is Sprint authority.
- GitHub **Milestone** is Release Target authority.
- Sprint completion does not force a release.
- Carry-over is allowed when work is incomplete.
- Expedite/hotfix work may bypass normal sprint sequencing without bypassing validation.
- Do not create placeholder Milestones merely to populate metadata; create one only for a real release target.

## Definition of Ready

A User Story, Bug, Task, Chore, or Technical Debt item is Ready when the applicable conditions are satisfied:

- scope is understandable;
- acceptance criteria are testable;
- required design decisions are resolved;
- dependencies are identified;
- security, data, migration, observability, and operational impact are considered;
- expected validation is known;
- Story Points are assigned when sprint planning requires them;
- no unresolved blocker prevents implementation.

## Definition of Done

Code complete and green branch CI are necessary but not sufficient.

A work item remains outside `Done` until applicable conditions are satisfied:

- implementation complete;
- automated tests for changed behavior pass;
- static, architecture, type, frontend, security, integration, runtime, migration, and other applicable quality gates pass;
- no known regression remains unresolved;
- documentation and contracts are aligned;
- security and migration implications are addressed;
- operational and observability impact is considered;
- work is integrated into `kaori/staging`;
- full staging CI passes;
- Local UAT is explicitly accepted;
- Issue/PR history contains relevant evidence.

Only then may the work item move to `Done`.

## CI and Quality Authority

Every governed implementation branch and `kaori/staging` must run the applicable full KAORI CI pipeline.

Caching may accelerate immutable dependency downloads, Docker layers, security databases, and deterministic build inputs. Cache must never bypass or reuse conclusions from:

- source linting;
- type checks;
- contract tests;
- functional/integration tests;
- frontend reproducibility;
- image scanning;
- runtime validation;
- migration validation;
- DAST;
- application logic assertions.

A green workflow badge is insufficient if logs contain unexpected skipped tests, tracebacks, assertion failures, HTTP 5xx responses, migration failures, or runtime failures.

## Failure Return Paths

- Failed implementation-branch CI → remain/return to `In Progress`; add `workflow:blocked` only when progress genuinely cannot continue.
- Failed staging CI → no UAT promotion; affected work returns to `In Progress` or remains blocked with evidence.
- Failed Local UAT → return to `In Progress` with UAT evidence.
- No failing or unaccepted change is promoted to `main`.

## Staging Integration and UAT

`kaori/staging` is the single integration and Local UAT branch.

Normal path:

```text
work branch
  -> full CI
  -> integrate to kaori/staging
  -> full staging CI
  -> Project Status UAT
  -> Local UAT
  -> explicit acceptance
  -> Done
```

The user syncs `kaori/staging` into the KAORI Dev Container for UAT. CI is machine verification; Local UAT is human acceptance.

## Main Promotion

Accepted increments are promoted through an explicit PR from `kaori/staging` to `main` when the release/promotion decision is made.

The default merge method is **merge commit**. PR creation and merge into `main` remain explicit human-controlled gates unless a future governance version changes that authority.

After merge, synchronize `kaori/staging` back to the exact `main` lineage using fast-forward when possible.

## Hotfix

Urgent production fixes use:

```text
main
  -> kaori/hotfix-<issue>-<slug>
  -> full CI
  -> applicable UAT
  -> PR to main
```

After the hotfix merges, synchronize `kaori/staging` from `main` before normal delivery continues.

## Label Authority

KAORI custom labels use the canonical namespaced vocabulary defined by `docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md`:

- `area:*`
- `scope:*`
- `quality:*`
- `impact:*`
- `workflow:*`

Labels must not duplicate Project Status, native Issue Type, Priority, Sprint, or Milestone.

## Branch Hygiene

Merged temporary branches are deleted when no active dependency remains. `main` and `kaori/staging` are the only default long-lived branches.

Before deleting a branch, verify that all required commits are represented in the destination lineage. `kaori/working` must not be deleted until issue #10 confirms that no required unique commit would be lost.

## Platform Governance Convergence

When Platform Governance / Platform Workflow standards are approved, KAORI converges through:

```text
KAORI local standard
  -> gap analysis
  -> terminology/policy mapping
  -> migration plan
  -> replace duplicated rules
  -> reference platform authority
  -> retain KAORI-specific extensions
```

The long-term lifecycle remains:

```text
Governance
  -> Policy
  -> Architecture Standards
  -> Work Management
  -> Secure SDLC
  -> CI / DevSecOps
  -> Release Governance
  -> Deployment / CD
  -> Operate
  -> Monitoring / Observability
  -> Incident / Problem Management
  -> Feedback to Backlog
```
