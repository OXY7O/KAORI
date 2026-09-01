# KAORI GitHub Project Setup

**Governance Version:** 1.1  
**Project:** KAORI  
**Scope:** Application-level work management and delivery governance  
**Repository Workflow:** `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`  
**Label Authority:** `docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md`

This document defines the application-local GitHub Project operating model for KAORI. Repository Issues remain the durable work records. GitHub Project/native fields supply planning and lifecycle metadata without recreating the same information inside Issue or Pull Request bodies.

## Metadata Authority

Use exactly one authority for each concern. Issue and PR bodies must not contain a duplicate `Project Metadata` table or equivalent metadata block.

| Concern | Authority |
| --- | --- |
| Lifecycle | GitHub Project `Status` |
| Work type | Native GitHub Issue Type |
| Priority | Project `Priority` |
| Estimate | Project `Story Points` |
| Planning cadence | Project `Sprint` iteration |
| Release target | GitHub Milestone |
| Ownership | GitHub Assignee / PR Reviewer |
| Portable context | Canonical repository Labels |
| Dependencies | Native Issue relationships / sub-issues |
| Development linkage | GitHub Development links / linked PRs |
| Implementation evidence | Issue → branch → PR → Actions → `kaori/staging` |
| Release artifact identity | Accepted staging SHA + immutable OCI digest |
| Human release acceptance | VPS UAT evidence tied to exact SHA + OCI digest |
| Production release identity | Semantic Versioning release + same approved OCI digest |

If connected tooling cannot update a Project/custom field, Native Issue Type, relationship, reviewer assignment, Milestone, or other requested GitHub-native metadata, it must tell the maintainer exactly which field and intended value require manual update. The body must not be used as a duplicate fallback authority.

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
- **Review** — implementation is under governed review/CI/integration assessment.
- **UAT** — accepted `kaori/staging` evidence is ready for the applicable human acceptance boundary. For release-bound work this includes immutable artifact publication and VPS UAT against the exact OCI digest.
- **Done** — the required delivery boundary is complete. For release-bound work this includes accepted VPS UAT, main promotion, Semantic Versioning release, production RUN verification, and rollback evidence.

Issue closure must not unconditionally force `Done`. A closed Issue without the applicable acceptance/final-delivery evidence is a governance inconsistency that must be corrected rather than normalized through automation.

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
- Expedite/hotfix work may bypass normal scheduling order without bypassing CI, security, migration, artifact, or UAT gates.

Sprint is planning cadence authority, not release authority.

## Release Target

GitHub Milestone is the release-target authority.

Create a Milestone only for a real release or bounded release-readiness target. Do not create placeholder Milestones merely to populate metadata. Sprint completion does not force a release.

A release-bound increment also carries artifact evidence outside Project custom fields:

- accepted `kaori/staging` SHA;
- approved Docker Registry image name;
- immutable OCI digest;
- digest-qualified VPS deployment reference;
- VPS UAT result;
- Semantic Versioning release identifier;
- production RUN result;
- previous known-good rollback digest.

The OCI digest is delivery evidence, not a substitute Project field.

## Issue Metadata Standard

Issue metadata is optional by applicability. A governed Issue may use:

1. Assignees.
2. Project membership.
3. Project `Status`.
4. Project `Sprint`.
5. Native Issue Type.
6. Project `Priority`.
7. Project `Story Points`.
8. GitHub Milestone.
9. Canonical labels.
10. Native relationships: parent, blocked by, blocking, related to, security alert where applicable.
11. Development linkage: work branch and Pull Request.

These values belong in GitHub-native/Project metadata. The Issue body contains the work contract, acceptance criteria, evidence, and concise relationship/development context only where useful to a human reviewer.

## Pull Request Metadata Standard

PR metadata is also optional by applicability. A governed PR may use:

1. Reviewers.
2. Assignees.
3. Canonical labels.
4. Project membership.
5. Project `Status`.
6. Project `Sprint`.
7. GitHub Milestone.
8. Development linkage to the governing Issue.

A PR does not need Priority, Story Points, or Native Issue Type merely because its controlling Issue has those values. Do not manufacture duplicate PR labels or body fields when the Project does not expose a field for the PR card.

## Canonical Project Views

The accepted KAORI Project contains nine governed views in this order.

### 00 - Work Register

**Purpose:** Broad operational register and metadata-audit surface.

Use this view to inspect the full governed work set and catch missing applicable Status, Type, Priority, ownership, Sprint, relationship, or development linkage. PR rows may legitimately leave Issue-only planning fields empty.

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

This view does not create extra lifecycle states for CI, staging, artifact publication, VPS deployment, code review, or release. Those remain evidence/activities inside the canonical lifecycle.

### 05 - Stabilization

**Purpose:** Isolate current quality, reliability, CI, runtime, migration, security, and release-exit work.

Use Native Issue Type, quality labels, relationships, and the active stabilization/release Milestone where applicable. Do not create a separate stabilization lifecycle.

Completed stabilization work remains traceable through closed Issues, merged PRs, commit history, Actions runs, artifact evidence, releases, and Milestone evidence.

### 06 - UAT & Release

**Purpose:** Show what still blocks an accepted increment.

Primary focus: work in `UAT`, current release-target work, linked PRs, accepted staging evidence, immutable OCI digest, VPS deployment, VPS UAT, Semantic Versioning release, and production RUN state.

For ordinary non-release increments, explicit Local UAT against accepted `kaori/staging` remains the human acceptance authority when applicable. For the artifact-backed release path, **VPS UAT** at `https://kaori.cloud` must reference the exact accepted staging SHA and deployed OCI digest. Work remains in `UAT` until the applicable acceptance and required promotion/release boundaries complete.

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
- Priority and ownership are assigned when useful;
- Story Points are assigned when sprint planning requires them;
- security, data, migration, observability, artifact, release, and operational impact are considered;
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
- work is integrated into `kaori/staging` through a governed PR;
- post-merge staging CI passes;
- applicable Local UAT is accepted;
- the accepted staging lineage is promoted through the required governed PR to `main`;
- relevant Issue/PR/CI/UAT evidence is recorded;
- applicable Project/native metadata is synchronized to the final state.

For work using the artifact-backed VPS/release path, `Done` additionally requires:

- the accepted staging SHA produced an **immutable OCI image** and recorded its **OCI digest**;
- the exact digest was deployed for **VPS UAT** at `https://kaori.cloud`;
- VPS UAT explicitly accepted that staging SHA + digest pair;
- main promotion introduced no unaccepted source drift;
- a valid **Semantic Versioning** release promoted/tagged the exact UAT-approved digest **without rebuilding** application bits;
- **production RUN** verification passed;
- the previous known-good digest is recorded as rollback evidence.

## Failure Return Paths

- Implementation/Draft Developer Check failure → remain or return to `In Progress` and repair before Ready.
- Full Admission or staging CI failure → do not enter UAT; return affected work to `In Progress` or record a genuine blocker.
- Artifact publish/digest verification failure → do not admit VPS UAT.
- Local UAT or VPS UAT failure → return to `In Progress` with UAT evidence and required corrections.
- Promotion PR failure, source drift, release digest mismatch, or production RUN failure → remain outside `Done` until corrected.
- Blocked work → retain its meaningful lifecycle Status and add `workflow:blocked` with blocker evidence.

No failing, drifted, or unaccepted increment is promoted to `main` or released.

## Label Usage

Use labels only for portable metadata not already owned by Project/native fields. The canonical families are:

- `area:*`
- `scope:*`
- `quality:*`
- `impact:*`
- `workflow:*`

GitHub's built-in `documentation` label remains the documentation authority. Exact names, colors, and descriptions are defined in `KAORI_GITHUB_LABEL_CATALOG.md`.

## GitHub UI Configuration Checklist

The Project v2 configuration is maintained in GitHub UI. Verify the following whenever Governance v1.1 is audited:

1. Status contains exactly the seven canonical lifecycle values.
2. Priority contains `Urgent`, `High`, `Medium`, and `Low`.
3. Story Points is numeric and uses `1, 2, 3, 5, 8` for governed estimates.
4. Sprint is a two-week Iteration field.
5. Work Type uses Native GitHub Issue Type rather than a duplicate custom Type field.
6. The nine views exist exactly in the documented order from `00 - Work Register` through `08 - Roadmap`.
7. Closed-Issue automation does not force `Done` before the required delivery boundary is complete.
8. PR cards may use applicable Project metadata and may leave Issue-only planning fields empty.
9. Label definitions remain aligned with the canonical label catalog.
10. Issue and PR bodies do not contain duplicate `Project Metadata` tables.
11. Release-bound work in `UAT` remains visible until immutable artifact identity, VPS UAT, main promotion, Semantic Versioning release, and production RUN evidence are complete.

The connected repository agent should update supported repository and Issue/PR metadata directly. Project v2 custom-field/view changes, Native Issue Type changes, relationships, or other metadata operations remain explicit GitHub UI operations whenever the available connector does not expose those mutations.

## Change Control

Any change to field semantics, lifecycle, view purpose, label authority, UAT authority, artifact authority, promotion authority, or release authority requires a governed repository change with relevant verification evidence. When centralized Platform Governance becomes authoritative, KAORI should converge through a versioned migration instead of maintaining a competing standard.
