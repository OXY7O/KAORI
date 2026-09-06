# KAORI Server, Examples, README, and Hero v1.7 Design

## Goal

Make KAORI's repository-facing deployment/runtime surfaces server-generic and easier to consume while completing the Hero contract so operational metadata and concise purpose remain stable in blocked/degraded states.

## Workstream A — Server and distribution boundary

### Canonical deployment path

`deploy/server/` becomes the only active host-deployment boundary. Existing VPS-named scripts are moved without changing trust, backup, migration, immutable-image, or verification behavior. Public/internal wording changes from VPS to Server where the term describes the deployment target rather than a historical artifact.

Canonical names:

- `deploy/server/README.md`
- `deploy/server/bootstrap-host.sh`
- `deploy/server/compose.server.yml`
- `deploy/server/deploy.sh`
- `deploy/server/verify.sh`
- `deploy/server/backup.sh`
- `deploy/server/restore.sh`
- `deploy/server/rollback.sh`
- `deploy/server/release-state.sh`

`KAORI_HOST*` environment variables remain unchanged because they already describe a generic server endpoint.

### Example boundary

`example/` remains an integration/demo boundary, not a CI-infrastructure boundary. `example/runner/` is removed. The root example documentation no longer lists a runner.

A new `example/kaori/` package provides a laptop-friendly runtime for an already-published admitted staging RC image. It does not create or publish a mutable `staging` image. The operator chooses the exact RC tag/digest in `example/kaori/.env`; the supplied defaults are disposable/local-only and may be overridden.

The local package owns:

- `compose.yml` — KAORI web plus PostgreSQL and Redis required for an interactive local instance;
- `.env.example` — local-only settings and image reference;
- `run.sh` — `start`, `status`, `logs`, `stop`, and `reset` actions;
- `README.md` — prerequisites and one-command usage.

The example favors a small interactive runtime rather than mirroring every staging worker. It must be explicit that full background Analytics/Reports behavior requires the governed server topology or additional worker services.

### Root README

The repository README is product-facing. It uses stable badges suitable for a private repository:

- CI — native GitHub workflow badge;
- Version — static repository release-train label tied to the maintained README contract, not a public shields query against a private release API;
- Python — static supported runtime version;
- License — static `Proprietary` label.

The architecture section becomes a high-level platform map suitable for repository visitors. Detailed module/runtime internals stay in `docs/architecture/README.md`.

## Workstream B — Hero v1.7

### Description density

Hero v1.7 replaces the previous 7–12-word-only rule with a semantic reference boundary defined by the approved examples.

Minimum reference:

> Operational visibility for cluster health, capacity, alerts, inventory, recommendations, and reporting.

Maximum reference:

> Automate Analytics PDF, XLSX, or CSV artifacts and Inventory XLSX/CSV exports with timezone-aware schedules and retained run evidence.

The verifier converts those references into deterministic word-count bounds and enforces the same bound for all source-resolvable Hero descriptions. Semantic clarity remains authoritative; the maximum is not a target.

### Metadata/state grammar

Operational Hero metadata is stable context, not readiness evidence. Therefore operational `normal`, `blocked`, and `degraded` states keep the metadata row visible. Blocked state changes the values to truthful setup/readiness semantics but must not remove the row.

Landing remains the only broad profile exception. Any other exception must be registered in the canonical Hero verifier and documented in `HERO.md`.

Kubernetes Analytics continues to use `page_hero.analytics_metadata(...)` with exactly three slots. The Storage Analysis blocked screenshot is a required regression case.

### CTA vocabulary

The cluster-readiness remediation CTA becomes `Open Cluster Integrations` and continues to target the orchestration/Kubernetes integration workspace with the same `clusters.manage` authorization boundary.

## Verification

Regression-first tests cover:

- no active `deploy/vps` path/reference;
- server deployment workflow and tests use `deploy/server`;
- `example/runner` is absent;
- local KAORI example has the required compose/env/script contract;
- root README badge labels and high-level architecture contract;
- Hero v1.7 reference bounds;
- blocked/degraded operational metadata persistence;
- Storage Analysis blocked metadata presence;
- Cluster Integrations CTA label/route/permission.

Developer Check is required on the exact work-branch SHA. After merge to `kaori/staging`, Full Admission is authority. An immutable RC must then be published and deployed through the governed staging-server workflow. Human UAT is the boundary before any `main` promotion.
