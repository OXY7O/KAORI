# KAORI Application Delivery Workflow

**Governance Version: 1.0**  
**Scope:** KAORI application repository  
**Authority:** Application-local baseline  
**Future Authority:** Platform Governance / Platform Workflow standards when formally adopted

## Lifecycle

`Idea / Request -> Epic -> User Story / Bug / Spike -> Refinement -> Ready -> issue-linked branch -> full CI -> kaori/staging -> full staging CI -> Local UAT -> Accepted -> PR to main -> merge commit -> main`

KAORI uses a closed-loop delivery model. Product ideas, operational findings, defects, technical debt, monitoring signals, and user feedback return to the backlog as governed work items.

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

`kaori/working` is retired after migration is verified. Temporary work branches are deleted after their changes are integrated and no active dependency remains. Issues, PRs, commits, releases, and governance records are the durable audit trail; stale branches are not retained for audit purposes.

## Work Branches

Normal governed work uses issue-linked temporary branches derived from the current `kaori/staging` baseline:

- `kaori/story-<issue>-<slug>`
- `kaori/bug-<issue>-<slug>`
- `kaori/task-<issue>-<slug>`
- `kaori/spike-<issue>-<slug>`
- `kaori/chore-<issue>-<slug>`
- `kaori/hotfix-<issue>-<slug>`

A descriptive temporary branch may be used for bootstrap work before an issue number exists, but it should converge to governed issue-linked work as soon as practical.

## Work Hierarchy

Canonical hierarchy:

`Epic -> User Story -> Task / Bug`

Spikes may attach to an Epic or Story to resolve uncertainty. Chores and Technical Debt may stand alone when appropriate or attach to a larger outcome. Native GitHub sub-issues are preferred when available.

## Sprint and Release

The default Sprint cadence is two-week and flexible.

- GitHub Project **Iteration** is Sprint authority.
- GitHub **Milestone** is Release authority.
- Sprint completion does not force a release.
- Carry-over is allowed when work is incomplete.
- Expedite/hotfix work may bypass normal sprint sequencing without bypassing validation.

## Definition of Ready

A User Story or Bug is Ready when the applicable conditions are satisfied:

- scope is understandable;
- acceptance criteria are testable;
- required design decisions are resolved;
- dependencies are identified;
- security, data, and migration impact are considered;
- expected validation is known;
- Story Points are assigned when sprint planning requires them;
- no unresolved blocker prevents implementation.

## Definition of Done

Code complete and green CI are necessary but not sufficient.

A work item remains in `UAT` until Local UAT from `kaori/staging` is explicitly approved. Applicable criteria include:

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

- Failed implementation-branch CI -> `In Progress` or `Blocked` with evidence.
- Failed staging CI -> no UAT promotion; return affected work to `In Progress` or `Blocked`.
- Failed Local UAT -> `In Progress` or `Blocked` with UAT evidence.
- No failing or unaccepted change is promoted to `main`.

## Staging Integration and UAT

`kaori/staging` is the single integration and Local UAT branch.

Normal path:

`work branch -> full CI -> integrate to kaori/staging -> full staging CI -> Local UAT -> Accepted`

The user syncs `kaori/staging` into the KAORI Dev Container for UAT. CI is machine verification; Local UAT is human acceptance.

## Main Promotion

Accepted increments are promoted through an explicit PR from `kaori/staging` to `main`.

The default merge method is **merge commit**. PR creation and merge into `main` remain explicit human-controlled gates unless a future governance version changes that authority.

After merge, synchronize `kaori/staging` back to the exact `main` lineage using fast-forward when possible.

## Hotfix

Urgent production fixes use:

`main -> kaori/hotfix-<issue>-<slug> -> full CI -> UAT -> PR to main`

After the hotfix merges, synchronize `kaori/staging` from `main` before normal delivery continues.

## GitHub Project Status Model

Canonical lifecycle statuses are:

- Backlog
- Refinement
- Ready
- In Progress
- Code Review / CI
- Staging
- UAT
- Blocked
- Done

Project Status is lifecycle authority. Repository labels must not duplicate these states with `status:*` labels.

## Branch Hygiene

Merged temporary branches are deleted when no active dependency remains. `main` and `kaori/staging` are the only default long-lived branches.

Before deleting a branch, verify that all required commits are represented in the destination lineage. `kaori/working` must not be deleted until comparison confirms that no required unique commit would be lost.

## Platform Governance Convergence

When Platform Governance / Platform Workflow standards are approved, KAORI converges through:

`KAORI local standard -> gap analysis -> terminology/policy mapping -> migration plan -> replace duplicated rules -> reference platform authority -> retain KAORI-specific extensions`

The target long-term lifecycle is:

`Governance -> Policy -> Architecture Standards -> Work Management -> Secure SDLC -> CI/DevSecOps -> Release Governance -> Deployment/CD -> Operate -> Monitoring/Observability -> Incident/Problem Management -> Feedback to Backlog`
