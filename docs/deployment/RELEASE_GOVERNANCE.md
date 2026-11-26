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

### Product version line versus exact release identity

The repository root `VERSION` file is the machine-readable **product version line** authority. It contains stable SemVer only, for example `0.3.0`, and is synchronized with the root README Version badge, the development `.env.example` `APP_VERSION`, and the application fallback used when no governed release metadata is injected.

`VERSION` is **not** the exact deployed release identity. Governed prerelease and stable identities remain release/deployment managed:

- product version line: `VERSION=0.3.0`;
- governed prerelease tag: `v0.3.0-rc.N`;
- governed prerelease runtime: `APP_VERSION=0.3.0-rc.N`;
- governed stable tag: `v0.3.0`;
- governed stable runtime: `APP_VERSION=0.3.0`.

The release workflow, Git tag, GitHub Release, accepted source SHA, OCI version/revision labels, immutable image digest, signature/provenance, and deployment receipt remain the authority for an exact candidate or stable release. A README badge or development default must never be used to infer which RC is deployed.

The approved first-public stable target is `v0.3.0`; the matching `VERSION` value is a planned product-version line, **not** proof of a published/accepted stable artifact. When the next product version line is approved, update `VERSION`, the README badge, development `APP_VERSION`, and application fallback together. Historical changelog sections and `docs/releases/KAORI_*.md` records remain immutable.

## Immutable Release Identity

Every production build must provide:

- `APP_VERSION`: canonical deployed KAORI Semantic Version, without the Git-tag `v` prefix. Examples: `2.3.0` or `0.1.0-rc.4`.
- `APP_BUILD_SHA`: exact Git commit used to build the image.
- `APP_BUILD_DATE`: immutable image creation/build timestamp supplied by the governed pipeline.

Git release tags use `v${APP_VERSION}` for stable releases and `v${APP_VERSION}` when `APP_VERSION` already contains an RC suffix. For example, application version `0.1.0-rc.4` corresponds to Git tag `v0.1.0-rc.4`. The `v` prefix belongs to the Git/release tag identity and is not part of `APP_VERSION` exposed inside the application.

`APP_BUILD_SHA` and `APP_BUILD_DATE` must describe the exact immutable image selected by release evidence. System Information may display these safe values but must never expose credentials, connection strings, provider secrets, or internal service endpoints.

The container image must additionally preserve the governed OCI identity annotations for source, revision, version, creation time, title, description, documentation, and license identity so a release candidate can be verified independently from mutable registry tags. KAORI's proprietary internal-use license is represented as the SPDX-compatible custom identifier `LicenseRef-KAORI-Internal-Use`, with the repository `LICENSE` file remaining the authoritative license text.

Production host configuration and release identity are separate authorities. Long-lived settings live in `/etc/kaori/app.env` (application policy), `/etc/kaori/secrets.env` (credentials, mode 0600), and `/etc/kaori/deploy.env` (deployment adapter); they are not rewritten for routine releases. The root `.env.production.example` is a deprecated pointer, not a monolithic runtime template. Governed deployment resolves the immutable image digest and Git release tag, normalizes the tag to `APP_VERSION` without its `v` prefix, and writes the generated `APP_VERSION`, `APP_BUILD_SHA`, `APP_BUILD_DATE`, and `KAORI_IMAGE` into `/var/lib/kaori/deploy-state/release.env` for the two-file Compose deployment.

## OCI image and supply-chain evidence contract

The immutable image digest remains the release authority. Mutable tags, README badges, SBOM filenames, provenance filenames, and GitHub Release assets are evidence or navigation surfaces; none may replace the accepted digest.

Each governed RC image must carry these OCI annotations:

- `org.opencontainers.image.source`
- `org.opencontainers.image.revision`
- `org.opencontainers.image.version`
- `org.opencontainers.image.created`
- `org.opencontainers.image.title`
- `org.opencontainers.image.description`
- `org.opencontainers.image.documentation`
- `org.opencontainers.image.licenses`

After the candidate is pushed and its immutable digest is captured, the RC workflow generates an SPDX JSON SBOM from that digest and a SLSA Provenance v1 predicate describing the accepted source SHA, candidate tag, workflow build type, builder identity, invocation, and build timestamps. Cosign v3.1.3 keyless GitHub OIDC attestations bind both predicates to the immutable digest. Cosign's v3 bundle format stores those attestations as OCI 1.1 artifacts whose manifest `subject` points to the image digest.

The RC workflow must verify both attestations immediately using the exact workflow certificate identity and GitHub OIDC issuer. Stable promotion must independently verify the accepted RC SBOM/provenance attestations before signing/promoting the same digest. Stable promotion must not regenerate SBOM or provenance because that would describe a different evidence event rather than the build that produced the accepted RC.

The stable release manifest records the accepted image digest, build date, and verification-evidence SHA256 values. Those hashes support auditability but do not supersede the registry digest.

## Changelog Contract

`CHANGELOG.md` is the source of truth for operator-relevant release history. Keep current work under `[Unreleased]` using only the sections that apply:

- `Added`
- `Changed`
- `Fixed`
- `Security`
- `Removed`

**Only after** the stable tag, GitHub Release and required production RUN verification succeed, move the actually published changes from `[Unreleased]` into a dated `## [X.Y.Z] - YYYY-MM-DD` entry through a separately reviewed PR. Before that event, keep planned changes under `[Unreleased]` and prepare human-reviewed per-version release notes; a planned RC is not a stable release. Historical audit documents are supporting evidence, not substitutes for the changelog.

## Release Procedure

1. Complete the pre-release audit, resolve blockers and select the intended Semantic Versioning increment; **source merge is not release authorization**.
2. Run `python scripts/verify_final_release.py --all --runtime` in the supported KAORI Dev Container/CI; retain mandatory checks and exact evidence.
3. Verify one Alembic migration head, executable prior-version upgrade tests, and database backup/rollback readiness.
4. When the next **product version line** is approved, update root `VERSION`, README badge, development `APP_VERSION` and application fallback together. Do not put RC/stable release identities in persistent host settings.
5. Admit increments to `kaori/staging` via reviewed issue-owned PRs, exact-head Developer Check, Full Admission and applicable Local UAT. This is frequent delivery, not production release.
6. Publish a signed `vX.Y.Z-rc.N` using existing `publish-staging-image.yml` from exact admitted staging SHA, by explicit request or the explicitly activated automatic staging train (#5243). Build once, record immutable OCI digest, labels, SPDX/SLSA, scan and verify.
7. Deploy that exact signed digest to the **operator-configured staging UAT target** only after target isolation/impact is approved; verify migration, backups, workers, health, edge and rollback. A shared staging/production target needs separately authorized production-impacting maintenance or a genuinely isolated non-public alternative. RC publication alone does not deploy a host.
8. Obtain explicit release-bound Human Acceptance for the actual deployed RC SHA, tag and digest, recorded in the existing `KAORI_APP_UAT_ACCEPTED:<source SHA>:<RC tag>:<OCI digest>` issue-comment format. CI or read-only inventory is not acceptance.
9. Promote accepted `kaori/staging` source to protected `main` using independently reviewed PR and post-promotion Full Admission. **No ordinary push or merge requests a release or deployment.**
10. Prepare and review `docs/releases/KAORI_X_Y_Z.md` using the canonical template: reader-facing Highlights, Improvements, Fixes, compatibility/security/operational impact and Known Limitations precede technical source/PR/digest evidence. Link exact RC and real Human UAT comment; admit by reviewed source PR.
11. Keep `CHANGELOG.md` under `[Unreleased]` until stable publication actually occurs. Never add a dated stable section merely because an RC exists or main promotion succeeded.
12. Only when the maintainer intentionally decides to ship, manually dispatch `release-image.yml` on protected `main`, specifying stable version and accepted RC. Unprivileged preflight verifies reviewed notes, real UAT evidence, source lineage, immutable digest and quality/security before native `production` Environment review.
13. Following independent `production` approval, verify the configured production target's committed receipt, accepted signed digest, DB/volume/network ownership, backup/rollback, health and provider ingress. Reconcile to the **same digest without rebuild** only if necessary; skip redundant deployment when the target already matches. **Actual runtime reconciliation is HOLD under #5094 pending #5093 operational UAT.** Do not equate publisher success with host deployment.
14. Only after successful production target reconciliation and verification, publish stable Git tag, registry `vX.Y.Z`/`vX.Y` aliases, release manifest and product-facing GitHub Release, retaining the accepted RC digest and provenance.
15. Verify System Information `APP_VERSION=X.Y.Z`, `APP_BUILD_SHA` and `APP_BUILD_DATE` agree with committed runtime receipt and immutable release; retain rollback digest and production RUN evidence.
16. **After actual publication**, create a separately reviewed `CHANGELOG.md` update moving shipped entries from `[Unreleased]` to dated stable history while preserving remaining work and closing release evidence.


The release pipeline follows **build once → verify → promote the same immutable digest**. A release workflow retry may reuse an existing candidate only after verifying its OCI version/revision identity. It must never rebuild after candidate verification and then publish the unverified rebuild as the same release.

## Release Gate

The static quality gate runs `scripts/verify_release_governance.py`. The verifier locks `VERSION` to the README badge and development/application fallback, preserves deployment-managed exact RC/stable identity, and rejects malformed source/default version metadata, active release identity accidentally persisted in `.env.production.example`, missing deployment-managed release injection in production Compose/VPS deployment, missing dated changelog/release-note structure, missing build-traceability variables, or a release process that is no longer documented. The master `python scripts/verify_final_release.py --all --runtime` gate additionally owns layered behavioral/security/rendering evidence, explicit E2E smoke, frontend reproducibility, migration integrity, endpoint registration, and production worker readiness; it delegates static/test/frontend work to `scripts/quality_gate.sh --all`. CI must provision the PostgreSQL/Redis services and required Reports worker rather than skipping those release tests.

Release publication adds evidence that is outside the source-only final verifier: immutable registry digest, candidate container scan, candidate runtime and migration validation, release DAST, SBOM/provenance, signature verification, digest-preserving promotion, release manifest, and GitHub Release publication.

Do not loosen a verifier, delete a required test, mark a failing layer as optional, move an existing release tag to another SHA/digest, or rebuild after release-candidate verification to approve a release. Fix the implementation, evidence, metadata, documentation, or release version instead.

## GitHub Environment deployment approval — Application #5081
Application release mutations follow the existing Website [two-Environment release approval](https://github.com/OXY7O/kaori-website/issues/201) pattern. The source-managed workflow binding is **not** sufficient to enforce human approval: effective protection rules must be verified by an administrator in GitHub Settings for this repository before activating these routes.

| Release job | Workflow | Environment | GitHub job purpose |
| --- | --- | --- | --- |
| Publish signed RC | `.github/workflows/publish-staging-image.yml` | `staging` | Accepted SHA and digest-bound RC metadata |
| Deploy RC to UAT host | `.github/workflows/deploy-staging-host.yml` | `staging` | Signed immutable RC, host mutation and rollback |
| Reconcile UAT public edge | `.github/workflows/reconcile-staging-publication.yml` | `staging` | Existing host/edge reconciliation after UAT deployment |
| Publish accepted stable | `.github/workflows/release-image.yml` | `production` | Stable tag/release/image-alias publication after verified main/RC lineage |

### Environment-configured runtime target (App #5093 / #5094)

Protected `kaori/staging` releases select GitHub Environment `staging`, while reviewed `main` stable publication selects `production`. **These are governance/credential/target selectors, never `single-slot`/`multi-slot` release modes.** The effective runtime depends on the operator's configured host/SSH trust, Compose project/service, state/receipt, volumes/network and provider-approved ingress. Many Environments can resolve to exactly the same runtime; one IP can host independent runtimes with separate project/state identities.

The #5093 implementation preserves the existing six staging/production GitHub Variables and five Secrets. `KAORI_HOST`, `KAORI_HOST_USER`, `KAORI_HOST_PORT` and `KAORI_HOST_DEPLOY_ROOT` select the VM and release root; the workflow derives the host-local config path (`/etc/kaori/deploy.env` for the canonical runtime, `/etc/kaori/targets/<project>/deploy.env` only when the deploy root explicitly selects `/opt/kaori/targets/<project>`). No additional GitHub Environment variable is required. The server adapter validates bounded Compose project, network, volume, state/receipt, backup, trust and config-root ownership before Docker/database mutation; all absent settings retain the approved current `kaori-production` defaults. The existing canonical shared-edge publication **fails closed for a configured distinct project** pending separate provider-owned routing approval. This is source-only work, **not yet hosted-UAT acceptance** of a distinct target. **Do not infer that setting a different IP/Environment name alone authorizes or safely initializes another runtime.** Issue #5093 owns full adapter validation and UAT; issue #5094 (blocked by #5093) owns production stable digest reconciliation/deployment.

At `production` approval, check the **configured production target's** actual committed receipt, signed image digest/OCI identity, health, recovery, and ingress authority. If already at the accepted UAT digest, publish stable release metadata without redundant deployment **only after the stable runtime version, committed rollback state and separately governed provider-edge evidence also agree**. If a configured target lacks that identity, require the separately reviewed deployment adapter, backup/rollback and provider-owned edge acceptance **before** stable publication. The #5116 read-only release-bound gate reuses `scripts/environment-credential-preflight.sh` inside the manual `release-image.yml` production job, after exact UAT evidence recheck but before registry login, signing or stable tag writes. It compares the selected Environment host/root, Compose project/network, all 12 application container references, private healthy PostgreSQL/Redis and immutable committed receipt to the accepted RC source SHA/digest and stable `APP_VERSION`. Only an exact healthy target with committed previous release and checksum-verified rollback backup is classified `READY_NOOP`. A valid different digest/source or runtime still reporting `0.3.0-rc.N` is `NEEDS_RECONCILIATION` **and terminates publication**, never a silent deployment; unsafe/missing target, health or recovery evidence is `BLOCK`. The adapter performs no host, database, registry or edge mutation. **#5117 must still implement and accept actual stable deployment/version/receipt convergence plus recovery and provider-edge verification before the first operational stable release.** Environment variables/secrets are currently repository-scoped unless the operator has independently migrated and confirmed scoped values.

**Release-sequencing rule:** The Human Accepted `v0.3.0-rc.1` digest, SHA and source-only promotion remain immutable. Do not merge target-adapter changes into its source lineage and then reuse that prior UAT acceptance as though a new runtime-changing image had been verified. New target capability requires its own issue, reviews, required gates and real non-public UAT before production activation.

**Administrator adoption (GitHub Settings → Environments):** Configure `staging` with deployment branches limited to the currently authorized `kaori/staging` and RC publisher `kaori/rc-request` refs; **remove `kaori/uat-request` from the staging deployment allowlist** (retired host trigger). Source integration or a ref push alone is not host deployment authorization. Keep existing Environment reviewer rules and operator-managed credentials. Configure `production` to permit **`main` only**, require independent `donibawono` approval, enable **prevent self-review**, and prohibit administrator bypass. Scope host credentials and registry variables/secrets to the correct Environment and verify migration from the previous `uat` name **without printing credential contents**. The legacy `uat` GitHub Environment must not remain an alternative privileged execution path. These settings cannot be installed or independently read through the connected GitHub tool: treat production release activation as **HOLD** until an administrator confirms them.

**Runbook negative gate:** From a valid previously accepted release request, verify that `Publish Stable` is **waiting for review** and has not reached the self-hosted runner, registry push, GitHub tag or VPS when `production` has no approval. Confirm reject/no-approval and self-review are blocked; then obtain `donibawono` independent **Approve and deploy** for an intentionally authorized run. Inspect job approval actor, protected branch ref, SHA, accepted RC digest, and release/host receipts. No dummy tag, synthetic production mutation or workflow bypass is authorized to prove the gate.

The existing immutable RC digest, source identity, publish preflight, signatures/SBOM/provenance, UAT acceptance, deployment and rollback controls remain authoritative. **Source-only promotions must not trigger a stable release**; stable release remains separately dispatched under the accepted release contract.

## GitHub Environment credential and SSH preflight (read-only) — #5093

The existing `.github/workflows/environment-credential-preflight.yml` reuses **the already configured** `staging`/`production` GitHub Environment variables and five encrypted secrets. It never provisions a VM, changes a server file, restarts Docker, deploys an image, publishes a tag or updates DNS. Runtime application configuration remains authoritative on the VM; there is **no GitHub `HOST_DEPLOY_ENV_FILE` setting or topology/slot-count mode**.

The first approved protected-staging merge of this workflow runs a **staging-only** preflight once (file-change-scoped push). Later runs are explicit CLI dispatches:

```bash
gh workflow run environment-credential-preflight.yml -R OXY7O/KAORI --ref kaori/staging -f target_environment=staging
# Only after reviewed main promotion and native production Environment reviewer approval:
gh workflow run environment-credential-preflight.yml -R OXY7O/KAORI --ref main -f target_environment=production
```

**Optional read-only runtime inventory (App #5093):** After the protected source is admitted, an operator may manually dispatch the **same** preflight with **inspect_runtime=true**. This is never enabled by the file-change-scoped staging push event; it does not add an Environment Variable, start another delivery engine, or mutate a host. The remote command reads only the allowlisted four-field committed release receipt, checks its immutable registry digest/source SHA/version and release directory, then inspects one running container per 12 Application services for matching image and OCI revision. It also checks the selected Compose project/network, web instance volume and private healthy PostgreSQL/Redis with their isolated named volume mounts. It prints only sanitized project, source SHA, version, digest and PASS/BLOCK status, not host identity, secrets, environment file contents or Docker inspect JSON.

```bash
# Manual inventory of the already-configured staging target (no image push/pull or deploy).
gh workflow run environment-credential-preflight.yml -R OXY7O/KAORI --ref kaori/staging -f target_environment=staging -f inspect_runtime=true

# Only after this code is protected-promoted to main and native production reviewer approval:
gh workflow run environment-credential-preflight.yml -R OXY7O/KAORI --ref main -f target_environment=production -f inspect_runtime=true
```

Inventory failure is evidence to investigate the **configured** target; never correct it by silently redeploying, changing Environment credentials, rewriting a receipt or reusing another project's volumes. An inventory PASS is a **read-only snapshot**, not proof of database privilege/transaction checks, migration, independent user/browser UAT, backup restore/rollback, ingress/provider-edge readiness, signed RC supply-chain validation, or authorization for stable publication. Continue to use the existing deploy/server/verify.sh and governed host/rollback UAT when separately approved. A distinct target must be provisioned and accepted independently; identical Environment names, SSH host/IP or Compose project names alone do not establish the same effective runtime.

The job fails closed on a wrong branch, absent credentials, mismatched registry/image prefix, unsafe deploy root, missing **pinned known_hosts**, rejected SSH key/passphrase, unreachable or untrusted VM, missing existing release receipt, or unavailable target Docker daemon. Registry login is stored only in a disposable hosted-runner config. Remote checks run as the configured SSH user and perform **existence/read-only inspections only**. Production requires a protected `main` branch and the actual GitHub `production` Environment review; a staging secret cannot be used to assert production readiness. No secret values or host files are printed.

A PASS proves credential transport and target access **at the time of the run**, not an accepted image digest, independent browser UAT, recovery, public-edge authority, or stable release. A failed check is an operational blocker; do not bypass it by switching to repository-level fallback secrets or running the normal deploy workflow as a test. Retain existing repository credentials until Environment-scoped preflight and required release checks are independently accepted.


## Intentional stable publication and readable change notes

Protected `main` source promotion is **not** a production release event. The existing `.github/workflows/release-image.yml` accepts only an explicit `workflow_dispatch` request for a stable version and an independently Human-UAT-accepted RC tag; no ordinary `push` or changelog commit requests production approval.

After actual release-bound UAT and before a stable request, prepare a human-reviewed `docs/releases/KAORI_X_Y_Z.md` using [the canonical template](../releases/RELEASE_NOTES_TEMPLATE.md). Record the exact candidate identity and the acceptance issue-comment URL, then include Highlights, Improvements, Fixes and Known Limitations. The existing release-governance verifier checks that file before privileged `production` publication, and the GitHub Release displays the reviewed narrative **before** authenticated source, immutable OCI digest, signature, SBOM, provenance and gate evidence. Missing or mismatched notes fail closed; generic raw SHA/digest-only release text is insufficient. Stable preflight must also authenticate the actual linked KAORI issue comment through the GitHub API, requiring a human owner/member author and the exact existing `KAORI_APP_UAT_ACCEPTED:<source SHA>:<RC tag>:<OCI digest>` acceptance line. A missing/unavailable/mismatched comment blocks the release **before** native `production` approval, and the publisher rechecks it after approval but before privileged registry or stable-tag writes. A correctly formatted link alone does not prove Human UAT.

Maintain material pending changes under `CHANGELOG.md` `[Unreleased]`, and add the dated stable entry **only after** the stable tag/Release is actually published. This does not weaken native production Environment review, digest/source-drift guards, host receipt/rollback validation, or the current HOLD on RC.2 deployment and Human Acceptance.


### Explicit host release deployment (App #5109)

The existing `.github/workflows/deploy-staging-host.yml` accepts a `workflow_dispatch` request from an operator or the authorized automatic RC publisher on the **current** protected `kaori/staging` SHA, specifying the exact published signed `vX.Y.Z-rc.N` candidate. A push to `kaori/uat-request`, any issue/PR commit, or a `main` merge **cannot** request host deployment. The admission job checks branch, SHA, prerelease tag, matching signed immutable image and Full Admission evidence before protected `staging` Environment secrets or SSH are used. The previous event branch is retired as a deployment trigger, not recreated as a new environment.

Both configured staging and production selectors may still resolve to the same canonical running host/Compose/database. **Before enabling automatic staging or manually dispatching deployment**, the operator must document the applicable production-impacting maintenance authorization (recurring scope/window for automation), backup/rollback and provider-edge readiness, or verify an actually distinct non-public target. Do not run a synthetic live deploy as a negative test. The source contract verifies that no `push` event is configured. Production stable publication remains a separate reviewed, manually dispatched `main` workflow; actual RC.2 operational UAT and stable reconciliation under #5093/#5094 stay on HOLD.

### Automatic staging release train (#5243)

- Repository Actions variable `KAORI_APP_AUTO_STAGING_ENABLED=true` explicitly activates the protected `kaori/staging` push train; missing, false or any other value disables it. Leave unset on first source admission. Confirm the native `staging` Environment branch restrictions, credentials, effective configured target, maintenance scope and recovery readiness before enabling. Do not override this variable inconsistently at Environment scope; use the repository variable as the activation authority. To disable, set it to false; cancel queued/in-progress requests before host mutation if immediate cessation is required.
- The existing publisher waits for exact post-merge staging Full Admission, serializes RC publication and preserves signed immutable evidence. Only newly published RCs from activated staging pushes request deployment; manual publication and `kaori/rc-request` remain publication-only fallback. Already-published source does not allocate another RC or automatically redeploy.
- Only the successful publication job can dispatch the existing staging deployment with exact candidate tag and publisher run ID. The receiver validates the pinned workflow path, push event, branch, SHA, successful terminal run, exact tag and artifact digest. Recheck current staging and activation before privileged host work; no automatic main/stable release or retired push-to-host path. The request is not deployment success.
- Manual recovery remains the existing staging dispatch with exact candidate tag and empty publisher run ID. If the automatic request job fails after publication, inspect the failure and rerun the failed job only after confirming the exact source and target remain current. Do not rerun successful host mutation blindly; inspect actual deployment receipt and rollback readiness first.
- Automatic qualification requires real hosted evidence after activation and separate Human Acceptance. This source change does not authorize a migration or a shared-target maintenance window by itself.
