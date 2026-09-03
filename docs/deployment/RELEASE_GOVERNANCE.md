# KAORI Release Governance

## Status

This document is the canonical release/version contract for KAORI. It governs version metadata shown in **Settings → General Settings → System Information**, Git tags, immutable application images, `CHANGELOG.md`, and the release-publication evidence produced by GitHub Actions.

The detailed CI/CD execution contract is documented in `docs/setup/GITHUB_ACTIONS_CI_CD.md`.

## Versioning

KAORI uses Semantic Versioning: `MAJOR.MINOR.PATCH`.

- `MAJOR`: incompatible product, API, data, or deployment contract changes.
- `MINOR`: backward-compatible product features or material capability additions.
- `PATCH`: backward-compatible defect fixes, cleanup, hardening, documentation corrections, and security fixes that do not change the product contract.

Pre-release audit work stays under `[Unreleased]` until the release candidate is approved. Do not bump `APP_VERSION` for every incremental review patch.

## Immutable Release Identity

Every production build must provide:

- `APP_VERSION`: canonical deployed KAORI Semantic Version, without the Git-tag `v` prefix. Examples: `2.3.0` or `0.1.0-rc.4`.
- `APP_BUILD_SHA`: exact Git commit used to build the image.
- `APP_BUILD_DATE`: immutable image creation/build timestamp supplied by the governed pipeline.

Git release tags use `v${APP_VERSION}` for stable releases and `v${APP_VERSION}` when `APP_VERSION` already contains an RC suffix. For example, application version `0.1.0-rc.4` corresponds to Git tag `v0.1.0-rc.4`. The `v` prefix belongs to the Git/release tag identity and is not part of `APP_VERSION` exposed inside the application.

`APP_BUILD_SHA` and `APP_BUILD_DATE` must describe the exact immutable image selected by release evidence. System Information may display these safe values but must never expose credentials, connection strings, provider secrets, or internal service endpoints.

The container image must additionally preserve the equivalent OCI identity labels for version, revision, and creation time so a release candidate can be verified independently from mutable registry tags.

Production host configuration and release identity are separate authorities. `/etc/kaori/.env.production` contains long-lived secrets and runtime configuration and is not rewritten for ordinary application releases. Governed deployment resolves the immutable application image and Git release tag, normalizes that tag to `APP_VERSION` by removing its leading `v`, supplies `APP_BUILD_SHA`/`APP_BUILD_DATE`, and injects those values into the production Compose transaction.

## Changelog Contract

`CHANGELOG.md` is the source of truth for operator-relevant release history. Keep current work under `[Unreleased]` using only the sections that apply:

- `Added`
- `Changed`
- `Fixed`
- `Security`
- `Removed`

Before a release, move approved entries from `[Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`. Historical audit documents are supporting evidence; they are not a substitute for the changelog.

## Release Procedure

1. Complete the ordered pre-release audit and close all release blockers.
2. Run `python scripts/verify_final_release.py --all --runtime` in the supported KAORI Dev Container/CI environment; this is the canonical final approval entry point and delegates to the underlying quality gates.
3. Confirm the Alembic migration graph has one head and retain an executable previous-supported-release upgrade-path check for release CI.
4. Select the Semantic Versioning increment from the approved changelog.
5. Update `APP_VERSION` defaults and development/source examples together. Do not add release-specific values to the persistent production host environment.
6. Move `[Unreleased]` changelog entries into the dated release section.
7. Create or update `docs/releases/KAORI_X_Y_Z.md` with the approved release scope, deferred work, verification command, and Git tag.
8. Commit and merge the reviewed release metadata change to `main`.
9. Start the manual release workflow for `X.Y.Z`; lock the exact approved `main` SHA and rerun the full KAORI CI and release preflight.
10. **Build the release candidate once** from that locked SHA, publish it first under the commit tag, and capture the immutable registry digest plus SBOM/provenance evidence.
11. Verify the exact candidate by digest with container vulnerability scanning, fresh-install migration, previous-supported-release upgrade migration, production runtime/worker readiness, full release DAST, and image signing.
12. Create or verify the annotated Git tag `vX.Y.Z` at the same approved SHA only after candidate verification succeeds.
13. **Promote the same immutable digest** to the governed `vX.Y.Z` and `vX.Y` registry aliases without rebuilding the image.
14. Verify every promoted tag resolves to the captured digest, generate `kaori-release-manifest.json`, and publish the GitHub Release from the approved release evidence.
15. Verify System Information receives `APP_VERSION=X.Y.Z` without the Git-tag `v` prefix plus the exact `APP_BUILD_SHA` and `APP_BUILD_DATE` represented by the released image and release manifest.
16. Preserve the image digest and release manifest so future deployment and rollback points remain unambiguous.

The release pipeline follows **build once → verify → promote the same immutable digest**. A release workflow retry may reuse an existing candidate only after verifying its OCI version/revision identity. It must never rebuild after candidate verification and then publish the unverified rebuild as the same release.

## Release Gate

The static quality gate runs `scripts/verify_release_governance.py`. The verifier rejects malformed source/default version metadata, active release identity accidentally persisted in `.env.production.example`, missing deployment-managed release injection in production Compose/VPS deployment, missing dated changelog/release-note structure, missing build-traceability variables, or a release process that is no longer documented. The master `python scripts/verify_final_release.py --all --runtime` gate additionally owns layered behavioral/security/rendering evidence, explicit E2E smoke, frontend reproducibility, migration integrity, endpoint registration, and production worker readiness; it delegates static/test/frontend work to `scripts/quality_gate.sh --all`. CI must provision the PostgreSQL/Redis services and required Reports worker rather than skipping those release tests.

Release publication adds evidence that is outside the source-only final verifier: immutable registry digest, candidate container scan, candidate runtime and migration validation, release DAST, SBOM/provenance, signature verification, digest-preserving promotion, release manifest, and GitHub Release publication.

Do not loosen a verifier, delete a required test, mark a failing layer as optional, move an existing release tag to another SHA/digest, or rebuild after release-candidate verification to approve a release. Fix the implementation, evidence, metadata, documentation, or release version instead.
