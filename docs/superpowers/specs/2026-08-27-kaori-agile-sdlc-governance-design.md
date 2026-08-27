# KAORI Agile SDLC Governance Design

**Version:** 1.0-design  
**Date:** 2026-08-27  
**Scope:** KAORI application repository  
**Authority:** Application-local governance baseline  
**Future authority:** Platform Governance / Platform Workflow standards when formally adopted

## 1. Purpose

This document defines the application-level work-management and SDLC operating model for KAORI. It is intentionally professional enough to govern current delivery while remaining easy to converge later with the wider Platform Governance and Platform Workflow standards.

The design covers intake, backlog management, Agile planning, branching, implementation, automated verification, staging integration, local UAT, pull requests, release readiness, and traceability. It does not attempt to replace future enterprise-level governance, policy, deployment, operations, incident-management, or observability standards.

KAORI therefore follows a **local-first, convergence-ready** model:

1. KAORI uses this document as its current application-delivery authority.
2. Platform-level standards may later supersede duplicated rules.
3. KAORI-specific extensions remain local where they are genuinely product-specific.
4. Migration to platform standards must be explicit, versioned, and traceable.

## 2. Governance Evolution

KAORI governance is versioned. New ideas, policy changes, branching changes, release changes, Definition of Done changes, or platform-standard adoption must not silently replace existing behavior.

Governance changes follow:

`Current Version -> Change Proposal -> Impact Review -> Agreement -> New Version -> Documentation/Workflow Migration -> Changelog`

Compatible refinements should increase the minor or revision level. Changes that materially alter lifecycle authority, branch semantics, UAT authority, release authority, or mandatory quality gates should increase the major governance version.

## 3. Lifecycle Model

The canonical KAORI delivery lifecycle is:

`Idea / Request -> Epic -> User Story / Bug / Spike -> Refinement -> Ready -> Implementation -> CI -> kaori/staging -> Local UAT -> Accepted -> PR to main -> Release / Operate / Observe`

The lifecycle is deliberately closed-loop. Operational findings, incidents, monitoring signals, technical debt, and user feedback should eventually return to the backlog as governed work items.

## 4. Branch Model

### 4.1 Permanent branches

- `main` is the production-ready baseline and release authority.
- `kaori/staging` is the permanent integration and local-UAT branch.

`kaori/staging` replaces the previous `kaori/working` role. The old branch may remain temporarily during migration, but new process documentation and future work must treat `kaori/staging` as authoritative.

### 4.2 Temporary work branches

Work must occur on purpose-specific branches derived from the current staging baseline unless an approved hotfix path applies.

Canonical naming:

- `kaori/story-<issue>-<slug>`
- `kaori/bug-<issue>-<slug>`
- `kaori/task-<issue>-<slug>`
- `kaori/spike-<issue>-<slug>`
- `kaori/chore-<issue>-<slug>`
- `kaori/hotfix-<issue>-<slug>`

Infrastructure/bootstrap work may use a descriptive branch such as `kaori/ci-cache` when no final issue number exists yet, but governed work should converge on issue-linked naming.

### 4.3 Integration flow

Normal flow:

`work branch -> full CI -> integrate to kaori/staging -> full staging CI -> local UAT -> accepted increment -> PR kaori/staging -> main -> full PR CI -> merge commit -> main`

After a successful merge to `main`, `kaori/staging` must be brought back to the exact main lineage using a fast-forward when possible.

### 4.4 Hotfix flow

Urgent production fixes may use:

`main -> kaori/hotfix-<issue>-<slug> -> CI -> UAT -> PR main`

After the hotfix merges, `kaori/staging` must be synchronized from `main` before normal delivery continues.

## 5. Agile Cadence

KAORI uses a **two-week sprint as the default planning cadence**, not as a mandatory release deadline.

The cadence is explicitly flexible:

- work may carry over when incomplete;
- scope may be adjusted during refinement;
- urgent production incidents may use an expedite/hotfix lane;
- spikes may be timeboxed independently;
- releases may occur when an accepted increment is ready rather than only at sprint boundaries.

The sprint exists to improve planning, focus, visibility, and inspect/adapt behavior. It must not encourage unfinished or unsafe work to be forced into `Done`.

## 6. GitHub Project Model

The GitHub Project named **KAORI** is the primary work-management surface.

### 6.1 Status field

Canonical statuses:

- Backlog
- Refinement
- Ready
- In Progress
- Code Review / CI
- Staging
- UAT
- Blocked
- Done

`Done` is reserved for accepted work. A story with complete code and green CI but without local UAT approval remains in `UAT`, not `Done`.

### 6.2 Type field

Canonical work-item types:

- Epic
- User Story
- Bug
- Task
- Spike
- Chore
- Technical Debt

### 6.3 Priority field

- P0 — Critical
- P1 — High
- P2 — Medium
- P3 — Low

### 6.4 Iteration field

The Project uses a two-week Iteration field for sprint planning. Iteration is the sprint authority; GitHub Milestones must not be used as sprint substitutes.

### 6.5 Story points

Canonical sizing scale:

`1, 2, 3, 5, 8, 13`

A story estimated above 13 points should normally be split before entering `Ready`.

### 6.6 Recommended views

- Product Backlog
- Current Sprint
- Active Delivery
- Staging & UAT
- Epics / Roadmap
- Bugs & Incidents
- Release Readiness

## 7. Work Hierarchy

Canonical hierarchy:

`Epic -> User Story -> Task / Bug`

Spikes may attach to an Epic or Story when they exist to resolve a specific uncertainty. Technical Debt and Chores may stand alone or attach to an Epic when part of a larger outcome.

Native GitHub sub-issues should be used where available. Acceptance-criteria checklists are not a substitute for child issues when the child item has its own lifecycle, owner, estimate, or evidence.

## 8. Work Item Contracts

### 8.1 Epic

An Epic must define:

- Outcome
- Problem Statement
- Business / Operational Value
- Scope
- Out of Scope
- Success Metrics
- Child Stories
- Risks
- Dependencies
- Exit Criteria

An Epic closes only when its exit criteria are met or it is explicitly cancelled/superseded.

### 8.2 User Story

Canonical narrative:

`As a <persona>, I want <capability>, so that <business or operational outcome>.`

A User Story must include:

- Acceptance Criteria using testable Given/When/Then or equivalent statements
- Definition of Ready evidence
- Technical Notes
- Security considerations where relevant
- Data/migration considerations where relevant
- Observability considerations where relevant
- Test Strategy
- Linked branch/PR
- UAT Evidence

### 8.3 Bug

A Bug must include:

- Observed Behavior
- Expected Behavior
- Reproduction
- Impact
- Root Cause
- Fix
- Regression Test
- UAT Evidence

Root cause must be understood before a permanent fix is accepted unless an emergency containment action is explicitly documented.

### 8.4 Task

A Task is implementation or operational work that has a concrete deliverable but does not independently represent user value. Tasks should normally belong to a Story, Bug, Epic, or governance activity.

### 8.5 Spike

A Spike must include:

- Question
- Hypothesis
- Timebox
- Evidence
- Decision
- Follow-up Stories / Tasks

A Spike produces learning or a decision. Experimental code from a spike must not silently become production code; production implementation requires a governed follow-up work item.

### 8.6 Chore and Technical Debt

Chores cover maintenance/admin work with no material product behavior change. Technical Debt captures known structural, quality, maintainability, performance, security, or reliability debt with explicit impact and an intended remediation outcome.

## 9. Definition of Ready

A User Story or Bug may enter `Ready` only when the applicable conditions are satisfied:

- scope is understandable;
- acceptance criteria are testable;
- required design decision is resolved or explicitly delegated to a bounded implementation decision;
- dependencies are identified;
- security/data/migration impact has been considered;
- story points are assigned when sprint planning requires them;
- no unresolved blocker prevents implementation;
- expected validation path is known.

Small urgent bugs may use an expedited Ready decision when impact justifies it, but the missing information must be documented as part of the work.

## 10. Definition of Done

KAORI `Done` means accepted increment, not developer-complete.

Applicable criteria include:

- implementation is complete;
- automated tests covering the changed behavior pass;
- static, architecture, type, frontend, security, integration, runtime, and other applicable quality gates pass;
- no known regression related to the change remains unresolved;
- migrations are safe and validated when applicable;
- documentation and contracts are updated when behavior or governance changes;
- observability/operational impact is considered where applicable;
- work is integrated into `kaori/staging`;
- full staging CI passes;
- local UAT from `kaori/staging` is explicitly approved;
- linked evidence is available in the Issue/PR history.

Only after these conditions are satisfied may the work item transition from `UAT` to `Done`.

## 11. Labels

Labels are portable metadata and must not duplicate Project fields unnecessarily.

### 11.1 Type labels

- `type:epic`
- `type:story`
- `type:bug`
- `type:task`
- `type:spike`
- `type:chore`
- `type:tech-debt`

### 11.2 Priority labels

Project Priority is the preferred authority. Priority labels may be retained for portability, automation, and search:

- `priority:p0-critical`
- `priority:p1-high`
- `priority:p2-medium`
- `priority:p3-low`

### 11.3 Area labels

Initial KAORI areas:

- `area:frontend`
- `area:backend`
- `area:reports`
- `area:intelligence`
- `area:kubernetes`
- `area:object-storage`
- `area:analytics`
- `area:integrations`
- `area:settings`
- `area:platform`
- `area:ci-cd`
- `area:security`
- `area:observability`

Area labels may expand as the product evolves, but broad overlapping labels should be avoided.

### 11.4 Impact labels

- `impact:breaking`
- `impact:migration`
- `impact:security`
- `impact:performance`
- `impact:accessibility`

### 11.5 Workflow exception labels

- `workflow:blocked`
- `workflow:expedite`

Project Status remains the source of truth for lifecycle state; labels such as `status:in-progress` or `status:done` must not be introduced.

## 12. Release Planning

GitHub Milestones are reserved for release targets such as `v2.4.0`, `v2.5.0`, or `v3.0.0`.

Traceability should support:

`Epic -> Story -> Sprint -> kaori/staging/UAT -> Release Milestone -> main`

A sprint and a release are independent concepts. A sprint is a planning cadence; a release is a governed product increment.

## 13. Pull Request Model

Work branches should integrate toward `kaori/staging`. Accepted staging increments are promoted through a PR from `kaori/staging` to `main`.

The default merge method is **merge commit**. Squash/rebase may not silently replace this policy.

PR evidence should identify:

- linked Issue(s);
- scope summary;
- acceptance criteria coverage;
- test/CI evidence;
- security/migration impact;
- UAT status when promoting staging to main;
- release impact.

PR creation and merge remain explicit human-controlled gates unless governance is formally revised.

## 14. Quality and CI Contract

Every governed implementation branch must run the applicable full KAORI CI pipeline. The pipeline must not be weakened to make a change pass.

Caching may optimize dependency downloads, Docker layers, security databases, and deterministic build inputs, but cache must not bypass:

- source linting;
- type checks;
- contract tests;
- functional/integration tests;
- frontend reproducibility;
- image scanning;
- runtime validation;
- DAST;
- migration validation;
- application logic assertions.

A green badge alone is insufficient if logs reveal unexpected skips, tracebacks, HTTP 5xx responses, migration failures, or suppressed assertions. CI evidence must be semantically healthy.

## 15. Local UAT Authority

`kaori/staging` is the canonical branch for local UAT.

The user syncs this branch into the KAORI Dev Container and performs acceptance testing. CI represents machine verification; local UAT represents human acceptance.

A work item remains in `UAT` until acceptance is explicit. Failed UAT returns the work to `In Progress` or `Blocked` as appropriate with evidence recorded.

## 16. Repository Artifacts to Implement

The implementation phase should introduce application-local governance artifacts, including:

- `.github/ISSUE_TEMPLATE/epic.yml`
- `.github/ISSUE_TEMPLATE/user-story.yml`
- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/task.yml`
- `.github/ISSUE_TEMPLATE/spike.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`

These artifacts must reflect this design and remain easy to replace or extend when Platform Governance standards are adopted.

## 17. Future Platform-Governance Convergence

When Platform Governance / Platform Workflow standards are ready, KAORI must migrate through a governed convergence process rather than copy both systems indefinitely.

Required sequence:

`KAORI local standard -> gap analysis -> terminology/policy mapping -> migration plan -> replace duplicated rules -> reference platform standard -> retain KAORI-specific extensions`

The target long-term lifecycle is:

`Governance -> Policy -> Architecture Standards -> Work Management -> Secure SDLC -> CI/DevSecOps -> Release Governance -> Deployment/CD -> Operate -> Monitoring/Observability -> Incident/Problem Management -> Feedback to Backlog`

This design intentionally stops short of defining enterprise-wide governance, deployment, operations, incident, and monitoring policy. Those are future convergence responsibilities.

## 18. Non-Goals

Version 1 does not attempt to:

- replace Platform Governance or Platform Workflow repositories;
- define organization-wide policy authority;
- introduce automatic PR creation or automatic merge;
- make sprint boundaries release deadlines;
- use Milestones as sprint tracking;
- duplicate Project Status in labels;
- bypass local UAT;
- weaken quality/security gates for delivery speed;
- create premature deployment/CD policy before the platform standard is ready.

## 19. Success Criteria

The governance implementation is successful when:

1. KAORI Project and repository metadata represent the lifecycle in this design.
2. New work can be entered as a professional Epic, Story, Bug, Task, Spike, Chore, or Technical Debt item.
3. Sprint planning is visible through a two-week Iteration with flexible carry-over/expedite behavior.
4. Work branches and Issues are traceable.
5. CI provides complete machine verification without cache masking logic errors.
6. `kaori/staging` is the single local-UAT integration branch.
7. `Done` is impossible by process definition before explicit local UAT acceptance.
8. Release milestones remain separate from sprint iterations.
9. The model can later be mapped to platform-level governance without rewriting the KAORI product lifecycle from scratch.

## 20. Version-1 Decision Record

The following decisions are locked for the first governance implementation:

- `main` = production-ready baseline.
- `kaori/staging` = permanent integration and local-UAT authority.
- work is performed on issue-linked temporary branches.
- default sprint cadence = two weeks, explicitly flexible.
- `Done` requires explicit local UAT approval.
- full CI precedes staging and release promotion.
- merge strategy to main = merge commit.
- Project Iteration = sprint authority.
- GitHub Milestone = release-target authority.
- governance evolves through explicit versioning.
- KAORI remains application-local until platform standards are ready for governed convergence.
