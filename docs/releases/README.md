# KAORI Release Lifecycle

KAORI separates the source-controlled **product version line** from the exact governed release identity.

The root `VERSION` file contains the current stable SemVer line, currently `0.3.0` as the approved first-public stable target. README and development defaults synchronize to that value so source presentation cannot silently drift. `VERSION` does not select or identify a deployed release candidate. A `0.3.0` source default does not mean a `v0.3.0` stable release exists; historical `v0.1.0-rc.*` releases remain separately preserved.

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

## Reviewed release notes and changelog

Production release is **intentional**, not triggered by routine commits or merges. After a release candidate has completed real UAT and received explicit Human Acceptance, the maintainer prepares a reviewed product-facing `docs/releases/KAORI_X_Y_Z.md` from [the release notes template](RELEASE_NOTES_TEMPLATE.md). It must identify the exact accepted RC and Human UAT issue-comment evidence, with clear **Highlights**, **Improvements**, **Fixes**, and **Known Limitations**. The linked GitHub comment must be a real explicit Human Acceptance authored by a trusted owner/member with the existing exact-line marker `KAORI_APP_UAT_ACCEPTED:<source SHA>:<RC tag>:<OCI digest>`. The stable workflow validates comment identity, author association and immutable SHA/tag/digest before and after native `production` approval; link syntax alone cannot authorize release.

The manual protected `main` stable release request validates the exact version and RC against that reviewed file before requesting privileged publication. The GitHub Release displays these understandable changes **first**, then appends verified OCI/SBOM/provenance/source evidence. Release highlights should explain audience, benefit, feature/fix or security/compatibility impact and known limitations in plain language. RC prerelease notes generated from `git log` are only engineering traceability and **must not** be copied as the final user-facing stable release summary. Signed stable metadata reuses the accepted candidate digest without rebuilding application bits.

`CHANGELOG.md` retains its `[Unreleased]` changes while stable publication is pending. **After the actual stable tag and GitHub Release exist**, move the accepted changes into a dated `[X.Y.Z] - YYYY-MM-DD` section in a separately reviewed update. Do not announce a prerelease as an already-published stable release.

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
