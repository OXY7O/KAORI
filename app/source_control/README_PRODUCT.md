# Source Control operational workspace — #3375

This product workspace follows approved domain authority [#559](https://github.com/OXY7O/KAORI/issues/559), separately from `Integrations → Source Control → GitHub` (connection registration, credentials, validation, jobs, lifecycle and synchronization).

## Current bounded Dev Container implementation

- `/source-control/` — Overview: active installation identities and committed collection coverage/status,
  with last committed observation. Its installation table shows the separately linked provider-native GitHub
  Account identity (native ID, observed login/type and observation time when available), or explicit unknown
  state when no matching account is observed. Account is **not** an App installation or KAORI Team.
  **No summed repository counts** across overlapping installations.
- `/source-control/repositories` — explicit installation selection and committed repository grants from SC-03's existing `read_installation_inventory` (search/visibility/archive, 5/10/25/50 pagination, default 5; branch/default-branch SHA only when committed).
- Existing GitHub integration routes remain the sole authority for validation, synchronization and mutation.
- GET reads committed KAORI database evidence; zero means a completed observed collection returned zero, **unknown does not mean zero**. Retained prior snapshots do not certify provider health or current freshness.
- Temporary UAT access is **local database Super Admin plus `integrations.manage`**, enforced independently of GitHub provider readiness for this product workspace. Provider setup/validation/sync remain guarded by their existing integration routes. This is NOT an accepted production resource authorization model. Global/non-admin repository visibility must remain denied until #724 implementation.
- Scoped UAT installation list has a bounded 50-row limit. The UI signals truncation; it does not advertise these sampled counts as complete organizational totals.

## Deferred Source Control product workstreams

- SC-04: pull-request/review/check/issue linkage evidence.
- SC-05: team engineering flow, review latency, throughput and responsibly interpreted DORA metrics. No developer ranking or velocity scores.
- SC-06: Actions run/job/attempt collection and exact-SHA CI evidence.
- SC-07: branch/ruleset/required review governance based on verified permissions.
- SC-08: releases, deployments, environment approvals and lineage.
- SC-09: cross-domain GitHub source SHA → CI → artifact digest → Registry/security → Kubernetes runtime → alert/incident.

Each needs its own committed collector/evidence contract, ownership, permission boundary, negative tests, and UAT before appearing as a data-backed operational tab. No guessed trend, CI success rate, DORA measurement, policy compliance or source-to-runtime link is acceptable.


## Approved workspace and ownership decision map — #4058

This is a decision index for the approved #4027 Source Control and #4028 Developer Workspace workstreams, **not** an assertion that deferred pages or provider capabilities are implemented. Preserve the current Violet Sidebar v2 and page-local navigation contract (#747/#748); do not create parallel global navigation for provider-specific operations.

| Approved responsibility | Current authority and maturity | Boundary |
| --- | --- | --- |
| Source Control Overview | Current bounded implementation (#3375, #4030): committed GitHub installation and observed account identity | Account, installation, organization and canonical Team are distinct; never infer cross-installation visibility |
| Organizations / Accounts and Repositories | Organizations full-workspace inventory is pending #4030; installation-scoped Repositories is currently bounded | Reuse the existing SC-03 repository inventory; Full Workspace Modal and server-side filters/pagination for expanded inventory, not a cloned data store |
| Pull Requests, Actions / CI, Branch Governance | Planned SC-04, SC-06, SC-07 under #4027 | Provider evidence and exact SHA precede checks, approvals or compliance claims |
| Engineering Flow and Releases / Deployments | Planned SC-05, SC-08 under #4027 | No fabricated DORA, developer ranking, deployment success or source-to-runtime lineage |
| Cross-domain lineage | Planned SC-09 under #4027 | Source Control supplies source evidence; Registry, Security, Kubernetes and operational owners retain their respective authority |
| Developer Self-Service versus Management | Planned persona experience under #4028 and #561 | Self-service requests cannot bypass Management approvals, server-side authorization or existing shared Jobs execution |
| Role Category, Service Catalog and Team | Planned #4060, #711/#723 and resource-scope #724 | Personas do not create grants; service ownership and Team identity are not provider GitHub account identities |

Provider capability differences belong to the provider-specific integration and collector contracts, not to universal UI promises. GitHub is the current bounded implementation; future providers require separately admitted capability/evidence mappings. Shared Jobs, Intelligence and Registry remain their canonical cross-domain owners (#440/#537 and existing domain authorities); Source Control may reference their committed evidence but must not duplicate their state machines.

Use existing HTMX partials, Full Workspace Modal, 5/10/25/50 server-side pagination (default 5), and evidence-first unknown/zero/degraded semantics. Every future management action requires permission and approval at its server-side boundary; a navigation item, role label, observed installation or successful read does not confer execution rights. The #724 resource-scope policy and negative authorization tests are prerequisites to non-admin or cross-installation exposure. Treat unresolved provider permission and persona decisions as pending authority review, not silently implemented behavior.

## QA/UAT (PENDING)

Use existing KAORI Ruff, djlint, pyright, pytest/contract, Sidebar Navigation Standard, Visual QA and Gherkin scenario catalog. Real Dev Container tests must prove 403 for non-authorized users; 404 for invalid installation; two-installation isolation; unknown versus verified zero; retained degraded snapshots; filters/5-default-pagination; no provider access during GET; light/dark/responsive/keyboard/HTMX. Record exact candidate SHA, provider scope, observed browser/DB evidence, and Human Acceptance. Official Developer Check, Full Admission, `kaori/staging`, `main` and release stay HOLD until authorization.
