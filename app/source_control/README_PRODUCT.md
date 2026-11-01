# Source Control operational workspace — #3375

This product workspace follows approved domain authority [#559](https://github.com/OXY7O/KAORI/issues/559), separately from `Integrations → Source Control → GitHub` (connection registration, credentials, validation, jobs, lifecycle and synchronization).

## Current bounded Dev Container implementation

- `/source-control/` — Overview: active installation identities and committed collection coverage/status, with last committed observation. **No summed repository counts** across overlapping installations.
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

## QA/UAT (PENDING)

Use existing KAORI Ruff, djlint, pyright, pytest/contract, Sidebar Navigation Standard, Visual QA and Gherkin scenario catalog. Real Dev Container tests must prove 403 for non-authorized users; 404 for invalid installation; two-installation isolation; unknown versus verified zero; retained degraded snapshots; filters/5-default-pagination; no provider access during GET; light/dark/responsive/keyboard/HTMX. Record exact candidate SHA, provider scope, observed browser/DB evidence, and Human Acceptance. Official Developer Check, Full Admission, `kaori/staging`, `main` and release stay HOLD until authorization.
