# KAORI Release, Demo, and Repository Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete cycle #188 through one staging integration candidate covering release completeness, runtime-artifact boundaries, repository presentation, standalone Docker Compose integration examples, terminal readability, scripts ownership, and branch hygiene.

**Architecture:** Keep production/runtime ownership unchanged. Introduce `example/` as a non-production integration-example boundary whose components are individually runnable Docker Compose stacks (Prometheus, Alertmanager, MinIO, Thanos, and runner example) and may also be combined by an optional aggregate compose file. Preserve `scripts/` for application-owned helpers, `deploy/` for governed live deployment, and `.github/` for CI/release authority.

**Tech Stack:** Docker Compose, Prometheus, Alertmanager, MinIO, Thanos, Bash, Python/pytest contract tests, GitHub Actions, Markdown.

**Spec:** GitHub parent #188 and children #189–#195.

## Global Constraints

- Tenant Management #61 and #112–#125 is excluded.
- Work integrates only to `kaori/staging`; no `main` promotion before maintainer review/UAT.
- Production environment values and secrets never appear in `example/`, README, release payloads, or tests.
- Each example component must be standalone and runnable through its own Docker Compose file.
- Production runtime artifacts must exclude `example/`, docs, tests, CI metadata, devcontainer/editor config, and runner/demo operations.
- Existing Full Admission, Trivy, Runtime/DAST, immutable digest, no-rebuild stable promotion, and source-lineage controls remain blocking.
- Test formatting fallout is repaired within the touched boundary rather than deferred to a catch-all cleanup.

---

### Task 1: Lock repository-hardening contracts

**Files:**
- Create: `tests/contracts/release/test_cycle_188_repository_hardening_contract.py`

- [ ] Add failing filesystem contracts for standalone example compose files, legal/security files, README logo/demo references, and runtime-artifact exclusion.
- [ ] Run Developer Check and record RED evidence before implementation.

### Task 2: Build standalone integration examples

**Files:**
- Create: `example/README.md`
- Create: `example/.env.example`
- Create: `example/compose.demo.yml`
- Create: `example/prometheus/compose.yml`, config and README
- Create: `example/alertmanager/compose.yml`, config and README
- Create: `example/minio/compose.yml`, README
- Create: `example/thanos/compose.yml`, config and README
- Create: `example/runner/compose.yml`, README and safe bootstrap example

- [ ] Keep every component independently runnable.
- [ ] Add an aggregate compose only as a convenience layer; standalone files remain authoritative examples.
- [ ] Document KAORI integration endpoints and environment overrides without real infrastructure values.

### Task 3: Harden runtime/release artifact boundaries

**Files:**
- Modify: `.dockerignore`
- Modify: `scripts/build_source_archive.sh` or add a dedicated runtime archive helper only if the existing source archive semantics must remain source-oriented.
- Modify release contracts/workflow only where required to preserve traceability and deterministic changelog/version evidence.

- [ ] Explicitly exclude `example/` and non-runtime repository surfaces from production runtime packaging.
- [ ] Keep evidence artifacts separate from runtime payloads.

### Task 4: Professional repository front and legal/security surfaces

**Files:**
- Modify: `README.md`
- Create: `LICENSE`
- Create: `SECURITY.md`

- [ ] Reuse `app/static/images/kaori-logo.svg` as the canonical README logo.
- [ ] Add restrained badges, Demo, Release, Security, License, and docs navigation.
- [ ] Use proprietary/internal-use licensing; do not present KAORI as OSI open source.

### Task 5: Standardize operator output and scripts ownership

**Files:**
- Create/modify only cycle-owned helpers and docs needed for consistent output.
- Audit `scripts/` paths and move example-only helpers under `example/`.

- [ ] Preserve raw diagnostics on failure while keeping normal output concise.
- [ ] Use canonical Development/Staging/Production and Host terminology.

### Task 6: Complete release/changelog staging candidate

**Files:**
- Modify release documentation/contracts/workflow only where gaps are proven.
- Modify `CHANGELOG.md` only to align the next governed release lifecycle; do not mint a stable release before maintainer acceptance.

- [ ] Ensure version/changelog/GitHub Release/Docker Hub/digest/source identities are mutually traceable.
- [ ] Do not rebuild accepted application bits during stable promotion.

### Task 7: Integrate and verify

- [ ] Run Developer Check on final cycle branch head.
- [ ] Merge one governed cycle PR to `kaori/staging` after GREEN.
- [ ] Wait for full staging Full Admission.
- [ ] Stop at staging and hand the exact SHA/evidence to the maintainer for review/UAT.
- [ ] Run branch-retirement audit after integration; delete only verified obsolete/merged refs.
