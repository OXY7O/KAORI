# KAORI Release Governance

## Status

This document is the canonical release/version contract for KAORI. It governs version metadata shown in **Settings → General Settings → System Information**, Git tags, immutable application images, and `CHANGELOG.md`.

## Versioning

KAORI uses Semantic Versioning: `MAJOR.MINOR.PATCH`.

- `MAJOR`: incompatible product, API, data, or deployment contract changes.
- `MINOR`: backward-compatible product features or material capability additions.
- `PATCH`: backward-compatible defect fixes, cleanup, hardening, documentation corrections, and security fixes that do not change the product contract.

Pre-release audit work stays under `[Unreleased]` until the release candidate is approved. Do not bump `APP_VERSION` for every incremental review patch.

## Immutable Release Identity

Every production build must provide:

- `APP_VERSION`: canonical deployed KAORI version and immutable image tag version.
- `APP_BUILD_SHA`: exact Git commit used to build the image.
- `APP_BUILD_DATE`: build timestamp supplied by the pipeline.

`APP_VERSION` must match the release Git tag and immutable image version. `APP_BUILD_SHA` and `APP_BUILD_DATE` must describe that exact image. System Information may display these safe values but must never expose credentials, connection strings, provider secrets, or internal service endpoints.

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
3. Confirm the Alembic migration graph has one head and test the production upgrade path against a staging PostgreSQL database.
4. Select the Semantic Versioning increment from the approved changelog.
5. Update `APP_VERSION` defaults and examples together.
6. Move `[Unreleased]` changelog entries into the dated release section.
7. Create or update `docs/releases/KAORI_X_Y_Z.md` with the approved release scope, deferred work, verification command, and Git tag.
8. Commit the release metadata change.
9. Create an annotated Git tag `vX.Y.Z` from the approved commit.
10. Build one immutable image from that tag and inject `APP_BUILD_SHA` and `APP_BUILD_DATE`.
11. Verify System Information shows the same version/build identity as the deployed image.
12. Preserve the image digest and deployment manifest so rollback points remain unambiguous.

## Release Gate

The static quality gate runs `scripts/verify_release_governance.py`. The verifier rejects malformed or divergent version defaults, a production image example that does not match `APP_VERSION`, missing dated changelog/release-note structure, missing build-traceability variables, or a release process that is no longer documented. The master `python scripts/verify_final_release.py --all --runtime` gate additionally owns layered behavioral/security/rendering evidence, explicit E2E smoke, frontend reproducibility, migration integrity, endpoint registration, and production worker readiness; it delegates static/test/frontend work to `scripts/quality_gate.sh --all`. CI must provision the PostgreSQL/Redis services required by those release tests rather than skipping them.

Do not loosen a verifier, delete a required test, or mark a failing layer as optional to approve a release. Fix the implementation, evidence, metadata, or documentation instead.
