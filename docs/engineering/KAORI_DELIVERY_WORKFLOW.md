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
  -> issue-linked work branch
  -> focused development verification
  -> Review
  -> PR to kaori/staging
  -> Full Admission once for the immutable source tree + authority fingerprint
     or exact evidence reuse when that pair is already admitted
  -> PR Integration
  -> kaori/staging integration
  -> Staging Integration (evidence reuse + fresh smoke)
  -> UAT
  -> explicit Local UAT acceptance
  -> Promotion
  -> PR kaori/staging -> main
  -> merge commit
  -> Post-promotion integrity
  -> Done
```

KAORI uses a closed-loop delivery model. Product ideas, operational findings, defects, technical debt, monitoring signals, and user feedback return to the backlog as governed work items.

Development feedback and governed Admission are separate boundaries. Ordinary issue-branch pushes do not need to spend 20–30 minutes recomputing the complete Admission suite. Focused checks run during implementation; comprehensive Admission is paid when a stable candidate reaches the staging Pull Request boundary.

## Human-Readable GitHub Standard

GitHub history is a long-lived engineering record. Titles, branches, commits, Pull Requests, comments, and CI evidence must be readable without reconstructing intent from source code.

### Issue titles

Native GitHub Issue Type is the type authority. Do not repeat the type in the title. Use sentence case, describe one outcome/problem, and omit a trailing period.

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

### Issue body

Every work item should make the following understandable to a reviewer:

1. Context / problem / outcome.
2. In scope and explicitly out of scope.
3. Testable acceptance criteria.
4. Dependencies and relationships.
5. Security, data, migration, observability, and operational impact where applicable.
6. Verification and UAT requirements.

Chronological execution evidence belongs in Issue comments. Keep the body as the current contract and use comments as the audit timeline.

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

### Pull Request titles and body

PR titles use the same Conventional Commit subject style. A KAORI PR is written for humans first and auditability second.

Canonical body reading order:

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
  -> Release Impact
  -> Reviewer Checklist
```

Use `Refs #<issue>` while work is still moving through staging/UAT. Use `Closes #<issue>` only on the final PR whose successful merge is intended to close the work item.

### Evidence comments

Technical comments should follow:

```text
## <Evidence / Investigation / Validation> — YYYY-MM-DD

### Context
### Result
### Evidence
### Decision / Next Step
```

Keep raw log dumps in GitHub Actions. Issue comments retain the evidence needed for a human to understand the decision without reading thousands of log lines.

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

`kaori/working` is retired only after issue #10 proves all required commits are represented in `kaori/staging`. Temporary work and validation branches are deleted after integration when no active dependency remains.

## Work Hierarchy

Canonical hierarchy:

```text
Epic
  -> User Story
     -> Task / Bug
```

Spikes may attach to an Epic or Story. Chores and Technical Debt may stand alone or attach to a larger outcome. Native GitHub parent/sub-issue relationships are preferred.

## Project Status Model

GitHub Project `Status` is the lifecycle authority:

1. `Inbox` — captured but not yet triaged.
2. `Backlog` — accepted for consideration/refinement.
3. `Ready` — Definition of Ready satisfied.
4. `In Progress` — implementation or remediation underway.
5. `Review` — implementation is ready for CI/review/integration assessment.
6. `UAT` — integrated staging evidence is ready for explicit Local UAT.
7. `Done` — Local UAT is accepted and Definition of Done is satisfied.

`workflow:blocked` is exception metadata, not a competing lifecycle Status. Refinement is a Backlog activity; staging is an integration authority; CI and code review are Review activities.

## Sprint and Release

The default Sprint cadence is two weeks and remains flexible.

- GitHub Project **Iteration** is Sprint authority.
- GitHub **Milestone** is Release Target authority.
- Sprint completion does not force a release.
- Carry-over is allowed when work is incomplete.
- Expedite/hotfix work may bypass normal sprint sequencing without bypassing validation.
- Do not create placeholder Milestones merely to populate metadata.

## Definition of Ready

A User Story, Bug, Task, Chore, or Technical Debt item is Ready when applicable conditions are satisfied: scope is understandable; acceptance criteria are testable; design decisions are resolved; dependencies are identified; security/data/migration/observability/operational impacts are considered; expected validation is known; Story Points are assigned when needed; and no unresolved blocker prevents implementation.

## Definition of Done

Code complete and Full Admission are necessary but not sufficient. A work item remains outside `Done` until applicable conditions are satisfied:

- implementation complete;
- automated tests for changed behavior pass;
- applicable static, architecture, type, frontend, security, integration, runtime, migration, DAST, and other quality authorities pass or are reused only through exact accepted evidence;
- no known regression remains unresolved;
- documentation and contracts are aligned;
- security and migration implications are addressed;
- operational and observability impact is considered;
- work is integrated into `kaori/staging`;
- Staging Integration passes;
- Local UAT is explicitly accepted;
- promotion lineage is verified when promoted to `main`;
- Issue/PR history contains relevant evidence.

## CI and Quality Authority

KAORI uses **Full Admission + exact evidence reuse** with a **validation authority fingerprint**.

The governing rule is:

> **Same immutable source tree + same validation authority fingerprint = never repeat comprehensive validation.**

### Development feedback

Ordinary issue-branch pushes are development activity, not a governed Admission boundary. GitHub Actions does not run the comprehensive pipeline for every `kaori/**` work-branch push.

During implementation, run focused local checks appropriate to the blast radius using existing KAORI quality commands and test suites. This keeps iteration fast while preserving the staging PR as the auditable comprehensive validation boundary.

### Full Admission boundary

The Pull Request to `kaori/staging` is the first governed Admission boundary for a normal work item.

A new source tree normally has no matching comprehensive evidence, so PR Integration reports **FALLBACK** and runs one Full Admission. Full Admission preserves all authoritative coverage:

- source linting and formatter checks;
- Pyright/type safety;
- architecture/import/reachability checks;
- contract and migration tests;
- functional/integration and domain characterization tests;
- frontend reproducibility;
- secrets/SAST/dependency/workflow security;
- production image build and vulnerability scan;
- runtime validation;
- DAST;
- application logic assertions;
- code-health ceilings and exact debt-ledger integrity.

A successful Full Admission publishes immutable evidence containing:

- source commit SHA;
- source tree SHA;
- validation profile version;
- **validation authority fingerprint**;
- run ID/attempt;
- workflow identity;
- every required comprehensive gate conclusion;
- timestamp.

### Validation authority fingerprint

The authority fingerprint is derived deterministically from the validation profile version and tracked Git identities for validation-authority files, including:

- `.github/workflows/**`;
- `.github/ci/**`;
- `requirements/**`;
- Admission policy helpers;
- `scripts/quality_gate.sh`;
- `scripts/verify_*`;
- release validation contracts;
- this delivery workflow authority;
- Dockerfile and compose authority.

An application change changes the source tree. A validation-authority change changes both the source tree and the authority fingerprint. Either condition invalidates older evidence and requires a new Full Admission once.

A validation-authority change does **not** mean repeating Full Admission at every later staging/main transition. Once the new tree + fingerprint has passed Full Admission, equivalent transitions reuse that evidence.

### Validation profiles

- **Full Admission** — comprehensive validation for a new tree/fingerprint or any forced fallback.
- **PR Integration** — evidence lookup before staging merge; a new tree falls back to Full, while an already admitted exact pair may reuse.
- **Staging Integration** — merge-parent/tree equivalence plus authority fingerprint verification and fresh smoke; produces the machine-verified Local UAT candidate.
- **Promotion** — verifies the exact UAT-selected staging tree/fingerprint and lineage before `main`.
- **Post-promotion** — verifies resulting main tree/fingerprint/lineage and performs fresh integrity smoke.

### Fail-closed evidence rules

Evidence is reusable only when all required identity and result checks pass. A missing, failed, skipped, cancelled, neutral, stale, ambiguous, wrong-profile, wrong-tree, or wrong-authority-fingerprint evidence record is not reusable.

A different commit SHA is allowed only at merge transitions where parent lineage proves that the merge preserves the admitted source and the resulting source tree is exactly the same as the admitted tree.

If equivalence cannot be proven, the workflow reports **FALLBACK** and executes Full Admission. A different tree or fingerprint always invalidates reuse.

Manual dispatch can always force Full Admission.

Caching may still accelerate immutable dependency downloads, Docker layers, security databases, and deterministic build inputs. Caches are not Admission evidence.

A green workflow badge is insufficient if required evidence contains unexpected skipped gates, tracebacks, assertion failures, HTTP 5xx responses, migration failures, or runtime failures.

## Human-Readable CI Evidence

Operator-facing CI output must be concise and stable. Vocabulary is limited to `PASS`, `FAIL`, `SKIP`, `REUSED`, and `FALLBACK`.

Every profile summary presents, in order:

1. Result.
2. Profile.
3. Commit SHA.
4. Tree SHA.
5. Evidence source/run.
6. Duration.
7. Coverage summary.
8. Fresh checks.
9. Reused checks.
10. First actionable failure only when failed.
11. One Next action.

Logical coverage is grouped into Foundation & Governance, Reports/Domain Contracts, Code Quality & Type Safety, Functional & Integration, Frontend, and Security & Runtime. Raw diagnostic logs remain available, but pytest progress dots and repetitive verifier prose must not dominate the operator summary.

## Failure Return Paths

- Failed Full Admission → remain/return to `In Progress`.
- Failed PR/Staging Integration → no staging/UAT progression; fix or FALLBACK to Full Admission.
- Failed Local UAT → return to `In Progress` with UAT evidence.
- Failed Promotion/Post-promotion → do not mark delivery complete.
- No failing or unaccepted change is promoted to `main`.

## Staging Integration and UAT

`kaori/staging` is the single integration and Local UAT branch.

Normal path:

```text
work branch
  -> focused development verification
  -> PR to kaori/staging
  -> Full Admission once for new tree/fingerprint
     or REUSED evidence for an already admitted exact pair
  -> integrate to kaori/staging
  -> Staging Integration (REUSED evidence + fresh smoke, or FALLBACK)
  -> Project Status UAT
  -> Local UAT
  -> explicit acceptance
```

The user syncs the exact accepted `kaori/staging` SHA into the KAORI Dev Container for UAT. CI is machine verification; Local UAT is human acceptance and must never be fabricated.

## Main Promotion

Accepted increments are promoted through an explicit PR from `kaori/staging` to `main`.

Promotion verifies that the PR head is the exact UAT-selected staging lineage, that `main` has not introduced incompatible drift, and that accepted tree/fingerprint evidence remains valid. Post-promotion verifies the resulting main tree and runs fresh integrity smoke. Ambiguity or identity mismatch triggers FALLBACK to Full Admission.

The default merge method is **merge commit**. After merge, synchronize `kaori/staging` back to the exact `main` lineage using fast-forward when possible.

## Hotfix

Urgent production fixes use:

```text
main
  -> kaori/hotfix-<issue>-<slug>
  -> focused development verification
  -> PR to main
  -> Full Admission for the final hotfix tree/fingerprint
  -> applicable UAT
  -> merge
```

After the hotfix merges, synchronize `kaori/staging` from `main` before normal delivery continues.

## Label Authority

KAORI retains GitHub's built-in `documentation` label. Custom labels use the canonical namespaced vocabulary in `docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md`:

- `area:*`
- `scope:*`
- `quality:*`
- `impact:*`
- `workflow:*`

Custom labels must not duplicate GitHub-native metadata. Native Issue Type remains the authority for Bug, Feature/User Story, Task, Chore, Technical Debt, Spike, and Epic; Project fields remain the authority for Status, Priority, and Sprint.

## Branch Hygiene

Merged temporary branches are deleted when no active dependency remains. `main` and `kaori/staging` are the only default long-lived branches. Before deleting a branch, verify that all required commits are represented in the destination lineage. `kaori/working` must not be deleted until issue #10 confirms that no required unique commit would be lost.

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
