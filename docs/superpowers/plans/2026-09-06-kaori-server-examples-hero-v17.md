# KAORI Server and Hero v1.7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize host deployment and repository examples while enforcing Hero v1.7 description/metadata parity through staging UAT.

**Architecture:** Keep deployment behavior unchanged while renaming its repository boundary from VPS to Server. Keep integration examples focused, add a small laptop runtime for admitted RC images, and extend the existing canonical Hero verifier instead of page-local exceptions. All delivery remains Issue → work branch → Developer Check → `kaori/staging` → Full Admission → immutable RC → staging server deployment.

**Tech Stack:** Flask/Jinja/HTMX, Docker Compose, Bash, GitHub Actions, Python contract verifiers, Tailwind, PostgreSQL, Redis.

**Spec:** `docs/superpowers/specs/2026-09-06-kaori-server-examples-hero-v17-design.md`

## Global Constraints

- `main` remains untouched until explicit human UAT acceptance.
- Existing pinned SSH trust, immutable image digest authority, backup-before-migration, migration, TLS, ingress, and runtime verification must remain fail-closed.
- `KAORI_HOST*` variable names remain unchanged.
- No mutable `staging` image tag is introduced.
- Hero metadata remains visible for operational normal/blocked/degraded states.
- Hero description bounds are derived from the two approved reference sentences in the spec.
- No production credential or private host value is added to examples.

---

### Task 1: Lock regression contracts before production changes

**Files:**
- Create/modify: `tests/contracts/release/test_server_deployment_boundary_contract.py`
- Create/modify: `tests/integrations/test_example_kaori_runtime_contract.py`
- Modify: `tests/integrations/test_hero_description_budget_contract.py`
- Modify/create: Kubernetes Analytics Hero contract coverage under `tests/kubernetes/` or `tests/contracts/analytics/`

**Interfaces:**
- Consumes: current `deploy/vps`, `example/runner`, Hero v1.6, `cluster_required_blocker()`.
- Produces: failing source-level contracts for the server path, local runtime example, Hero v1.7 bounds/metadata parity, and CTA wording.

- [ ] Add assertions that active deployment references use `deploy/server` and `compose.server.yml`, and reject `deploy/vps` / `compose.vps.yml`.
- [ ] Add assertions that `example/runner/` is absent and `example/kaori/{compose.yml,.env.example,run.sh,README.md}` exists with start/status/logs/stop/reset semantics.
- [ ] Add Hero v1.7 tests that derive the lower/upper reference word counts and reject descriptions outside that range.
- [ ] Add blocked Storage Analysis contract asserting `page_hero.analytics_metadata(...)` remains present and blocked values are supplied rather than conditionally dropping the row.
- [ ] Add CTA contract requiring `Open Cluster Integrations`, `url_for('integrations.kubernetes')`, and unchanged `clusters.manage` permission.
- [ ] Commit test-only RED evidence before production changes.

### Task 2: Rename the governed deployment boundary

**Files:**
- Move: `deploy/vps/*` → `deploy/server/*`
- Rename: `deploy/server/compose.vps.yml` → `deploy/server/compose.server.yml`
- Modify: `.github/workflows/deploy-staging-host.yml`
- Modify: deployment/release docs and contract tests that reference the old path
- Modify: scripts under `deploy/server/` whose user-facing output or variables still say VPS when describing the deployment target

**Interfaces:**
- Consumes: same environment files, image digest, source SHA, release version, SSH inputs.
- Produces: behaviorally equivalent server-generic deployment path.

- [ ] Copy each current deployment file to the canonical `deploy/server/` path without changing behavior.
- [ ] Update internal default path from `compose.vps.yml` to `compose.server.yml`.
- [ ] Replace user-facing `VPS` wording with `Server` where it names the target topology; retain historical references only when they are intentionally archival.
- [ ] Update staging workflow SCP/chmod/deploy paths to `deploy/server`.
- [ ] Update all active tests/docs/verifiers that own deployment paths.
- [ ] Delete the obsolete `deploy/vps/` files only after all references point to the server path.
- [ ] Run targeted release/deployment contracts and commit.

### Task 3: Clean the example boundary and add laptop runtime

**Files:**
- Delete: `example/runner/Dockerfile`
- Delete: `example/runner/README.md`
- Delete: `example/runner/compose.yml`
- Delete: `example/runner/entrypoint.sh`
- Create: `example/kaori/compose.yml`
- Create: `example/kaori/.env.example`
- Create: `example/kaori/run.sh`
- Create: `example/kaori/README.md`
- Modify: `example/README.md`
- Modify: root `README.md`

**Interfaces:**
- `run.sh ACTION [IMAGE]` supports `start|status|logs|stop|reset`.
- Compose consumes `KAORI_IMAGE`, local PostgreSQL/Redis values, `SECRET_KEY`, and bootstrap admin settings from `.env`.

- [ ] Remove Runner from the provider table and standalone behavior documentation.
- [ ] Create a local-only Compose stack with PostgreSQL, Redis, and KAORI web using `${KAORI_IMAGE}`.
- [ ] Add health checks and a localhost port mapping suitable for laptop UAT.
- [ ] Add `run.sh` that copies `.env.example` to `.env` on first start, accepts an optional exact RC image override, validates Docker Compose availability, and implements start/status/logs/stop/reset.
- [ ] Document that the admitted staging image is the current RC/tag/digest, not a mutable `staging` tag.
- [ ] Document limitations: background Analytics/Reports workers are not fully mirrored by the minimal laptop example.
- [ ] Run example contract tests and commit.

### Task 4: Simplify root README and architecture presentation

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/README.md`
- Create: `docs/architecture/kaori-platform-overview.svg` only if a repository-native visual remains clearer than a compact Mermaid/text alternative.

**Interfaces:**
- Root README remains product-facing.
- `docs/architecture/README.md` remains technical authority.

- [ ] Replace badge set with CI, Version, Python, License using non-empty stable values suitable for a private repository.
- [ ] Remove the disposable Runner from root standalone-example text.
- [ ] Add the laptop runtime example link and one-command usage.
- [ ] Replace the low-level Browser → Flask → services ASCII architecture with a high-level Platform → Evidence Sources → Governed Operations → Outputs view.
- [ ] Keep detailed runtime/component links in architecture docs.
- [ ] Run documentation/static contracts and commit.

### Task 5: Implement Hero v1.7 copy-density and metadata parity

**Files:**
- Modify: `docs/design/components/HERO.md`
- Modify: `scripts/verify_hero_component_standard.py`
- Modify: `app/templates/components/page_hero.html` only if shared state/profile ownership needs a renderer change
- Modify: affected operational Hero templates/wrappers discovered by the verifier
- Modify: `app/common/dependencies.py`
- Modify: affected family contracts/verifiers

**Interfaces:**
- Canonical description bounds are derived from the approved minimum and maximum reference sentences.
- Operational Hero metadata is required in `normal`, `blocked`, and `degraded` states.
- `cluster_required_blocker()['action_label'] == 'Open Cluster Integrations'`.

- [ ] Update Hero standard to v1.7 and remove the broad blocked-metadata reduction exception.
- [ ] Extend the canonical verifier to enumerate operational Hero consumers/states and reject deterministic branches that omit metadata.
- [ ] Keep Kubernetes Analytics exactly-three-slot metadata ownership through `analytics_metadata(...)` for blocked state.
- [ ] Audit Dashboard, Analytics, Inventory/Operations/Governance, Reports, Object Storage, Integrations, and admin Hero families for metadata parity; repair all deterministic omissions found.
- [ ] Update description-bound logic to the approved reference range and normalize only descriptions that violate the new range.
- [ ] Change CTA label to `Open Cluster Integrations`; keep route and permission unchanged.
- [ ] Run canonical Hero verifier plus routed family tests and commit.

### Task 6: Freeze candidate and integrate to staging

**Files:**
- No new product files unless CI exposes a proven stale contract/formatting issue.

- [ ] Run/fetch Developer Check on exact final work-branch SHA.
- [ ] Inspect full failing logs for any red gate and repair only proven root causes through the same Issue/branch.
- [ ] Review final PR diff, review threads, and base freshness.
- [ ] Mark PR Ready only after exact-SHA Developer Check GREEN.
- [ ] Squash/merge to `kaori/staging` so temporary implementation commits do not pollute staging history.

### Task 7: Full Admission, immutable RC, and staging-server UAT deployment

**Files:**
- Delivery refs only: `kaori/rc-request`, `kaori/uat-request`.

- [ ] Wait for exact staging Full Admission to pass Static & Governance, Security, Functional, Frontend, Runtime & DAST, and CI Admission.
- [ ] Fast-forward `kaori/rc-request` to the exact admitted staging SHA.
- [ ] Verify RC workflow passes build, Trivy, runtime/DAST, tag reservation, registry uniqueness, push/pull, digest evidence, and GitHub prerelease.
- [ ] Fast-forward `kaori/uat-request` to the same SHA.
- [ ] Verify Release Evidence resolves exactly one RC and immutable digest.
- [ ] Verify server deployment passes PostgreSQL/Redis health, pre-migration backup, runtime config, migration, worker/runtime verification, HTTPS readiness, DNS/redirect, TLS, ingress, unknown-host rejection, and Certbot renewal dry-run.
- [ ] Record RC tag, source SHA, immutable digest, URL, backup path, and deployment run in Issue #218.
- [ ] Leave Issue #218 open at UAT and leave `main` untouched until the maintainer explicitly reports UAT PASS.
