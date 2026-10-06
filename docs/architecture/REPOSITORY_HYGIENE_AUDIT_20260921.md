# KAORI Repository Hygiene Audit — 2026-09-21

Status: current repository-hygiene authority for post-UAT hardening issue #475.

## Scope

This audit classifies repository surfaces outside the application package and records the authority that prevents obsolete support files from returning. It covers the repository root, `scripts/`, `example/`, `deploy/`, `docker/`, generated artifacts, and historical documentation.

Removal requires evidence. A file is not obsolete merely because it is old, deprecated, or historical.

## Classification

### Active runtime, build, and release authority

Retain:

- root runtime/build entrypoints: `Dockerfile`, `compose.yml`, `compose.production.yml`, `run.py`, `celery_worker.py`, `gunicorn.conf.py`;
- canonical release identity and release documentation: `VERSION`, `CHANGELOG.md`, `README.md`, `SECURITY.md`, `LICENSE`;
- development environment authority: root `.env.example` plus `.devcontainer/`;
- production environment/deployment authority: `deploy/env/` and `deploy/server/`;
- runtime container entrypoint: `docker/entrypoint.sh`;
- current CI, release, source-hygiene, architecture, reachability, and verification tools under `scripts/`;
- immutable migrations and current release evidence referenced by release governance.

The root `.env.production.example` is retained only as an explicit deprecation/redirect surface. It is not a production configuration authority; the split templates under `deploy/env/` remain authoritative.

### Active examples and operator references

Retain `example/` because it contains supported provider and operator reference surfaces:

- Alertmanager;
- Prometheus;
- Thanos;
- MinIO;
- KAORI RC/example runtime;
- standalone `shared-edge/`;
- demo Compose/environment/bootstrap material.

These examples are not production configuration authorities, but they are intentional compatibility and operator references and therefore are not repository debris.

### Historical/archive material

Retain `docs/archive/` and reviewed historical/audit documents when they are explicitly historical and are not referenced as current runtime, release, environment, or operational authority.

Current archived scope includes `docs/archive/integration-cutover/`.

Historical material may explain prior decisions, but current executable contracts, canonical architecture documents, deployment documentation, and verifiers take precedence.

### Generated/local artifacts

Generated artifacts must not be committed:

- repository-root ZIP archives such as `OX.zip`;
- `__pycache__/`;
- `*.pyc` and `*.pyo`;
- local test/lint/type-check caches.

`.gitignore`, source-hygiene checks, and `scripts/verify_obsolete_files.py` enforce the relevant source-tree constraints.

### Obsolete support helper retired by #475

`scripts/cleanup_obsolete_files.sh` is retired.

Reason:

- it duplicated a large historical list of already-retired paths;
- it performed destructive local cleanup rather than providing a fail-closed release contract;
- canonical obsolete-path enforcement already belongs in `scripts/verify_obsolete_files.py`;
- domain final-lock verifiers retain direct absence assertions where domain semantics require them.

The retirement exposed stale registry reads in Object Storage, Core Workspace, Core Kubernetes, Platform Operations, and Integrations final-lock verifiers. Those dependencies were removed and any missing retired-path ownership was moved into the canonical obsolete-file verifier.

## Canonical prevention model

Repository hygiene is now enforced through existing authorities only:

1. `scripts/verify_obsolete_files.py` — canonical fail-closed registry for files that must never return, plus generated Python/root-artifact checks.
2. `scripts/verify_module_reachability.py` — prevents unowned/unreachable Python implementation from silently accumulating.
3. `scripts/verify_source_hygiene.sh` — source-tree hygiene.
4. `scripts/verify_architecture_boundaries.py` and package/domain verifiers — preserve architectural ownership after removal.
5. `scripts/verify_release_surface_coverage.py`, `scripts/verify_release_governance.py`, and `scripts/verify_final_release.py` — protect release/deployment surfaces from accidental cleanup.
6. Domain final-lock verifiers — retain domain-specific absence assertions where a removed compatibility surface is part of a locked contract.

No replacement destructive cleanup script is introduced.

## Removal rule

A future deletion under repository hygiene requires all of the following:

- no current runtime/import/template/workflow/operator reference;
- no release/deployment/environment authority role;
- no required migration or immutable evidence role;
- no supported example/operator-reference role;
- explicit replacement or retirement semantics when the file previously owned a contract;
- existing reachability, architecture, source-hygiene, and release gates remain green.

## #475 implementation evidence

Repository-side implementation was intentionally incremental because staging Full Admission revealed hidden consumers of the retired cleanup registry:

- PR #512 retired `scripts/cleanup_obsolete_files.sh`;
- PR #513 removed the stale Object Storage final-lock dependency and moved its retired paths into the canonical obsolete-file authority;
- PR #514 removed the Core Workspace cleanup-registry dependency and consolidated 16 retired paths;
- PR #515 removed the Core Kubernetes cleanup-registry dependency;
- PR #516 removed the Platform Operations and Integrations cleanup-registry dependencies and completed missing global obsolete-path coverage.

The expected terminal state is one global obsolete-file registry plus domain-specific direct absence checks, with no consumer depending on the retired cleanup helper.

## Relationship to the 2026-08-01 audit

`docs/architecture/UNUSED_FILE_AUDIT_20260801.md` remains historical evidence for the earlier cleanup cycle. Its former statement that `scripts/cleanup_obsolete_files.sh` is a prevention authority is superseded by this document and the current verifier model above.
