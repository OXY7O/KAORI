# KAORI Release Lifecycle

KAORI separates the source-controlled **product version line** from the exact governed release identity.

The root `VERSION` file contains the current stable SemVer line, for example `0.2.0`. README and development defaults synchronize to that value so source presentation cannot silently drift. `VERSION` does not select or identify a deployed release candidate.

Exact prerelease identity is governed by `vX.Y.Z-rc.N`, and exact stable identity is governed by `vX.Y.Z`. The release/deployment workflow supplies the matching `APP_VERSION` plus source SHA, build date, OCI identity, and immutable digest. Development example defaults are never evidence that a specific RC or stable artifact is deployed.

## Stable release identity

A completed stable release must bind all of the following to one accepted lineage:

- Git tag `vX.Y.Z`.
- GitHub Release `KAORI vX.Y.Z`.
- accepted release-candidate tag.
- accepted application source SHA.
- immutable OCI digest.
- Docker Hub image tag `vX.Y.Z`.
- OCI `org.opencontainers.image.version` label/runtime version metadata.
- validation/signature evidence.
- changelog section for the released version and date.
- rollback identity: previous stable version/source/digest where available.

Stable promotion must reuse the exact digest accepted in Staging Acceptance. It must promote **without rebuilding application bits**.

## Changelog boundary

`CHANGELOG.md` keeps a top-level `[Unreleased]` section during development. Before stable publication, the accepted release scope is copied into a dated `[X.Y.Z] - YYYY-MM-DD` section and a fresh `[Unreleased]` section is retained for subsequent work.

Historical `docs/releases/KAORI_*.md` files are detailed records only. They do not override the current Git tag/GitHub Release/OCI release authority.

## Release artifacts

Production distribution has two distinct artifact classes:

1. **Runtime payload** — the production OCI image and `kaori-runtime-vX.Y.Z.zip`; application-only content required to run KAORI.
2. **Release evidence** — manifests, validation logs, scan/DAST output, signatures, and provenance retained separately as GitHub Actions/GitHub Release evidence.

The runtime payload excludes tests, `example/`, `.github/`, docs, Dev Container files, editor configuration, runner/bootstrap tooling, CI verification tooling, and private environment files.

Build a local runtime package with:

```bash
bash scripts/build_runtime_archive.sh 0.1.1
```

## Completion sequence

```text
Full Admission
→ Staging Validation
→ Staging Acceptance
→ Production Promotion
→ stable SemVer/tag
→ same accepted OCI digest promoted to Docker Hub stable tag
→ GitHub Release + changelog + runtime artifact + evidence
```

A release is incomplete if version identity, changelog, source lineage, or digest identity disagree.
