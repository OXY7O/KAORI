# KAORI GitHub Project Setup

**Governance Version:** 1.0  
**Project:** KAORI  
**Scope:** Application-level work management and delivery governance  
**Repository Workflow:** `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`  
**Label Authority:** `docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md`

This document defines the application-local GitHub Project operating model for KAORI. Repository Issues remain the durable work records. The Project supplies planning and lifecycle views without recreating native GitHub metadata.

## Metadata Authority

Use exactly one authority for each concern:

| Concern | Authority |
| --- | --- |
| Lifecycle | GitHub Project `Status` |
| Work type | Native GitHub Issue Type |
| Priority | Project `Priority` |
| Estimate | Project `Story Points` |
| Planning cadence | Project `Sprint` iteration |
| Release target | GitHub Milestone |
| Ownership | GitHub Assignee |
| Portable context | Canonical repository Labels |
| Dependencies | Native Issue relationships / sub-issues |
| Implementation evidence | Issue → branch → commits → PR → Actions → `kaori/staging` → Local UAT |

Do not duplicate these authorities with alternate custom fields or labels.

PR cards are integration evidence, not a second planning work item. When GitHub Project does not expose Issue-only planning metadata such as Priority, Story Points, Sprint, or Native Issue Type on a PR card, leave those values empty. Do not recreate them with labels.

## Canonical Lifecycle

Configure `Status` with exactly these values and preserve this order:

1. `Inbox`
2. `Backlog`
3. `Ready`
4. `In Progress`
5. `Review`
6. `UAT`
7. `Done`

Lifecycle semantics:

- **Inbox** — captured but not yet triaged.
- **Backlog** — accepted for consideration/refinement but not admitted to delivery.
- **Ready** — Definition of Ready is satisfied and implementation may begin.
- **In Progress** — active implementation, remediation, or investigation is underway.
- **Review** — implementation is ready for governed CI/review/integration assessment.
- **UAT** — integrated `kaori/staging` evidence is ready for explicit human acceptance.
- **Done** — all applicable automated gates pass and Local UAT is explicitly accepted.

Issue closure must not unconditionally force `Done`. A closed Issue without accepted UAT evidence is a governance inconsistency that must be corrected rather than normalized through automation.

A blocked condition uses `workflow:blocked` while retaining the most meaningful lifecycle Status.

## Native GitHub Issue Type

Use Native GitHub Issue Type as the single work-type authority:

- Epic
- User Story
- Bug
- Task
- Spike
- Chore
- Technical Debt

Do not create a duplicate custom Type field, type labels, or title prefixes that restate the native type.

## Priority

Configure Project `Priority` with exactly:

- `Urgent` — immediate production, security, data-integrity, or delivery blocker.
- `High` — important work expected in the nearest governed delivery window.
- `Medium` — normal planned work without immediate urgency.
- `Low` — non-urgent improvement, cleanup, or optional follow-up.

Priority is Issue/work-item planning metadata. It is not required on PR cards.

## Story Points

Use a numeric Project field named `Story Points`.

Planning scale:

`1, 2, 3, 5, 8`

Work estimated above 8 should normally return to refinement and be decomposed before entering `Ready`. Epic points remain empty unless a future governance version explicitly changes that rule.

## Sprint

Use a Project Iteration field named `Sprint`.

- Default cadence: two weeks.
- Carry-over is allowed for incomplete work.
- Backlog items not admitted to a sprint remain unscheduled.
- Epic sprint assignment is optional; prefer scheduling executable child work rather than using the Epic as the commitment record.
- Expedite/hotfix work may bypass normal scheduling order without bypassing CI, security, migration, or UAT gates.

Sprint is planning cadence authority, not release authority.

## Release Target

GitHub Milestone is the release-target authority.

Create a Milestone only for a real release or bounded release-readiness target. Do not create placeholder Milestones merely to populate metadata. Sprint completion does not force a release.

## Canonical Project Views

The accepted KAORI Project contains nine governed views in this order.

### 00 - Work Register

**Purpose:** Broad operational register and metadata-audit surface.

Use this view to inspect the full governed work set and catch missing Status, Type, Priority, ownership, Sprint, or relationship metadata. PR rows may legitimately leave Issue-only planning fields empty.

### 01 - Inbox

**Purpose:** Untriaged intake queue.

Primary filter: `Status = Inbox`.

Use this view to decide whether work is rejected, needs clarification, or is admitted to Backlog.

### 02 - Backlog & Ready

**Purpose:** Separate accepted future work from delivery-ready work without inventing additional lifecycle states.

Primary statuses: `Backlog`, `Ready`.

Backlog work is not a sprint commitment by default. Ready work must satisfy the applicable Definition of Ready.

### 03 - Current Sprint

**Purpose:** Primary sprint execution view.

Filter to the current Sprint iteration. Surface executable work across `Ready`, `In Progress`, `Review`, `UAT`, and `Done` as appropriate for the active iteration.

Prefer compact Issue metadata: Type, Priority, Assignee, Story Points, and Status. PR cards remain review/integration evidence and may have planning fields empty.

### 04 - Delivery Flow

**Purpose:** Visualize governed movement through delivery.

Emphasize:

`Ready → In Progress → Review → UAT → Done`

This view does not create new lifecycle states for CI, staging, or code review. Those are evidence and activities inside the canonical lifecycle.

### 05 - Stabilization

**Purpose:** Isolate current quality, reliability, CI, runtime, migration, and release-exit work.

Use Native Issue Type, quality labels, relationships, and the active stabilization/release Milestone where applicable. Do not create a separate stabilization lifecycle.

Completed stabilization work remains traceable through closed Issues, merged PRs, commit history, Actions runs, and Milestone evidence.

### 06 - UAT & Release

**Purpose:** Show what still blocks an accepted increment.

Primary focus: work in `UAT`, current release-target work, linked PRs, and explicit acceptance evidence.

Only explicit Local UAT against the accepted `kaori/staging` lineage can satisfy the human acceptance gate for work that requires UAT.

### 07 - Bugs & Debt

**Purpose:** Keep defects and Technical Debt visible beside planned product delivery.

Use Native Issue Type filters for **Bug** and **Technical Debt**. Do not recreate those classifications as labels.

Sort or group by Priority when useful.

### 08 - Roadmap

**Purpose:** Higher-level outcome and planning visibility.

Prefer Epics and material User Stories. Show Milestone/Sprint context where useful, but do not turn Roadmap placement into lifecycle or release authority.

## Definition of Ready

A User Story, Bug, Task, Chore, or Technical Debt item is normally `Ready` when applicable conditions are satisfied:

- scope and expected outcome are understandable;
- acceptance criteria are testable;
- dependencies and relationships are identified;
- Priority and ownership are assigned;
- Story Points are assigned when sprint planning requires them;
- security, data, migration, observability, and operational impact are considered;
- expected verification is known;
- no unresolved blocker prevents implementation.

A Spike is ready when the question, hypothesis, timebox, evidence expectation, and decision output are clear.

## Definition of Done

Automated CI success is required but is not sufficient by itself.

Applicable work reaches `Done` only when:

- implementation is complete;
- required automated tests and quality gates pass;
- no known regression remains unresolved;
- documentation/contracts are aligned;
- security and migration implications are addressed;
- operational/observability impact is considered;
- the work is integrated into `kaori/staging`;
- full staging CI passes;
- explicit Local UAT is accepted where required;
- Issue/PR history contains the relevant evidence.

## Failure Return Paths

- Implementation-branch CI failure → remain or return to `In Progress` unless an active correction is still appropriately under `Review`.
- Staging CI failure → do not enter UAT; return affected work to `In Progress` or record a genuine blocker.
- Local UAT failure → return to `In Progress` with UAT evidence and required corrections.
- Blocked work → retain its meaningful lifecycle Status and add `workflow:blocked` with blocker evidence.

No failing or unaccepted increment is promoted to `main`.

## Label Usage

Use labels only for portable metadata not already owned by Project/native fields. The canonical families are:

- `area:*`
- `scope:*`
- `quality:*`
- `impact:*`
- `workflow:*`

GitHub's built-in `documentation` label remains the documentation authority. Exact names, colors, and descriptions are defined in `KAORI_GITHUB_LABEL_CATALOG.md`.

## Issue and PR Metadata

### Governed Issue

Once accepted into the governed backlog, an Issue should normally have:

- Project `KAORI`;
- Native Issue Type;
- Status;
- Priority;
- Assignee;
- canonical labels as needed;
- Story Points and Sprint when scheduled/estimable;
- Milestone only when targeting a real release;
- Parent/sub-issue or dependency relationships where applicable;
- implementation branch/PR once development starts.

### Pull Request

A PR should carry:

- human-readable title and canonical PR body;
- linked controlling Issue;
- appropriate repository labels when useful;
- branch and exact SHA evidence;
- CI evidence;
- impact and UAT state;
- release impact.

Do not force Issue-only planning metadata onto PR cards.

## GitHub UI Configuration Checklist

The Project v2 configuration is maintained in GitHub UI. Verify the following whenever Governance v1 is audited:

1. Status contains exactly the seven canonical lifecycle values.
2. Priority contains `Urgent`, `High`, `Medium`, and `Low`.
3. Story Points is numeric and uses `1, 2, 3, 5, 8` for governed estimates.
4. Sprint is a two-week Iteration field.
5. Work Type uses Native GitHub Issue Type rather than a duplicate custom Type field.
6. The nine views exist exactly in the documented order from `00 - Work Register` through `08 - Roadmap`.
7. Closed-Issue automation does not unconditionally force `Done`.
8. PR cards are permitted to leave Issue-only planning fields empty.
9. Label definitions remain aligned with the canonical label catalog.

The connected repository agent may update repository content and Issue metadata, but Project v2 field/view changes remain explicit GitHub UI operations when the available connector does not expose those mutations.

## Change Control

Any change to field semantics, lifecycle, view purpose, label authority, UAT authority, or release authority requires a governed repository change with contract-test updates and evidence. When centralized Platform Governance becomes authoritative, KAORI should converge through a versioned migration instead of maintaining a competing standard.
