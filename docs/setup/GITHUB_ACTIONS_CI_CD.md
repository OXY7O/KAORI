# KAORI GitHub Actions CI/CD Design

## Status

**Design baseline — approved architecture, not yet an executable workflow implementation.**

This document captures the agreed KAORI source-control, CI, release, and container-publication workflow. It complements `docs/setup/GITHUB_ACTIONS_SELF_HOSTED_RUNNER.md`.

The implementation must preserve the existing KAORI quality and release-governance contracts. Existing verification entry points remain authoritative; GitHub Actions orchestrates them rather than replacing or weakening them.

---

## Goals

The CI/CD flow must provide:

- one stable daily working branch that is easy to sync to the developer laptop;
- deterministic full CI for every working-branch change, including small changes;
- explicit local Dev Container review before a pull request is allowed to proceed;
- pull-request validation against the current `main` integration result;
- explicit human approval before merge;
- curated Semantic Versioning release preparation;
- an isolated GitHub `release` Environment for privileged publication;
- Docker Hub as the production image registry;
- release-candidate validation against the actual container artifact;
- **build once, verify, then promote the same immutable digest**;
- SBOM, provenance, vulnerability scanning, signing, release manifest, and GitHub Release evidence;
- no direct production deployment in the initial rollout.

---

## Locked Decisions

### Repository branches

Daily development uses one long-lived branch:

```text
kaori/working
```

Normal work does not create a new branch per task. The working branch is reused continuously so the developer laptop can remain on the same branch.

Exceptional branches are allowed only when isolation is operationally necessary, for example:

```text
kaori/hotfix/<slug>
release/vX.Y.Z
```

The assistant must explicitly tell the user when a local branch switch is required.

### Merge strategy

Pull requests from `kaori/working` use **merge commits**.

Do not use squash merge or rebase merge for the long-lived working branch because the working branch must remain fast-forwardable to the resulting `main` history.

After a successful merge:

```bash
git fetch origin
git switch kaori/working
git merge --ff-only origin/main
git push origin kaori/working
```

The remote working branch must then be the base for the next change.

The branch must not be automatically deleted after merge. Protect `kaori/working` from deletion and force-push.

### Human acceptance boundary

Automated CI is not sufficient to authorize a PR or merge.

The normal approval flow is:

```text
assistant push
    ↓
working-branch CI passes
    ↓
developer syncs kaori/working
    ↓
developer tests in the KAORI Dev Container
    ↓
developer says "lanjut PR"
    ↓
PR is created
    ↓
PR integration CI passes
    ↓
developer says "merge"
    ↓
merge commit to main
```

No workflow automatically creates a PR or merges one.

### Full-CI policy

Every change on `kaori/working` runs the full CI cycle by default, including small changes such as wording, CSS, documentation, template adjustments, or a one-line backend fix.

The initial implementation intentionally avoids broad `paths-ignore` shortcuts.

Optimization may be introduced only after enough CI evidence exists to prove that a safe fast path does not create a verification blind spot.

### Runner selector

All self-hosted jobs use the agreed selector:

```yaml
runs-on:
  - self-hosted
  - linux
  - x64
  - kaori-ci
```

Initial runner identity:

```text
Runner family     : kaori-ci
GitHub runner     : kaori-ci-01
VM hostname       : kaori-ci-runner-01
Service account   : github-runner
```

### Host/runtime boundary

The runner VM is an executor, not the KAORI application runtime.

The host provides:

```text
Linux
GitHub Actions Runner
Docker Engine
Docker Buildx
Docker Compose plugin
base runner prerequisites
```

Python, Node.js, npm tooling, native PDF/build libraries, PostgreSQL, Redis, DAST tooling, and KAORI dependencies run in containers.

The CI implementation should use a repository-owned Docker/Compose CI environment so the runner host remains distribution-agnostic.

### Docker Hub release registry

Production release images are published to Docker Hub.

GitHub Environment:

```text
release
```

Initial required Environment secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

Initial Environment variable:

```text
DOCKERHUB_IMAGE
```

Example value:

```text
<dockerhub-namespace>/kaori
```

`DOCKERHUB_TOKEN` must be a scoped Docker Hub access token rather than an account password.

Working-branch and PR CI must not receive Docker Hub release credentials.

The built-in GitHub `GITHUB_TOKEN` is used for Git tag and GitHub Release operations; it is not stored as an Environment secret.

Keyless image signing should use GitHub OIDC where supported, requiring workflow permission:

```yaml
id-token: write
```

and no persistent signing private key.

### Release image tags

Release publication uses:

```text
<image>:X.Y.Z
<image>:X.Y
<image>:sha-<commit>
```

Example:

```text
<namespace>/kaori:2.4.0
<namespace>/kaori:2.4
<namespace>/kaori:sha-9876543
```

The release contract does not depend on `latest`.

All promoted release tags must resolve to the **same immutable OCI digest**.

---

# Source-Control Lifecycle

## Normal working flow

```text
main
  │
  └──► kaori/working
            │
            ├── implementation
            ├── commit
            └── push
                   │
                   ▼
            FULL WORKING CI
                   │
                   ▼
                 GREEN
                   │
          ┌────────┴────────┐
          ▼                 ▼
     GitHub state       laptop sync
                            │
                            ▼
                      Dev Container
                            │
                            ▼
                     human validation
                            │
                      "lanjut PR"
                            │
                            ▼
                        PR → main
                            │
                            ▼
                    merge-result CI
                            │
                          GREEN
                            │
                         "merge"
                            │
                            ▼
                      merge commit
                            │
                            ▼
                           main
                            │
                            ▼
                 fast-forward kaori/working
```

Laptop sync remains simple:

```bash
git fetch origin
git switch kaori/working
git pull --ff-only origin kaori/working
```

---

# CI Trigger Matrix

| Event | Full CI | Local review required | Release secrets | Publishes release image |
| --- | --- | --- | --- | --- |
| Push to `kaori/working` | Yes | Before PR | No | No |
| Pull request to `main` | Yes | Already required before PR; merge still explicit | No | No |
| Push/merge to `main` | Yes | No additional local gate required for the exact merge | No | No |
| Release preparation PR | Yes + release metadata validation | GitHub review | No | No |
| Manual `Release` workflow | Yes + final release/candidate gates | GitHub `release` Environment approval | Yes | Yes |

The same policy applies to small and large code changes.

---

# CI Gate Architecture

The full CI cycle is ordered from cheaper checks to more expensive runtime checks. This reduces wasted runner time when an early gate fails.

## Gate 1 — Source hygiene and existing static quality

Reuse the existing KAORI entry points rather than duplicating them in YAML.

Primary existing command:

```bash
bash scripts/quality_gate.sh --static
```

Coverage includes the current KAORI static, architecture, migration, formatting, type, and contract checks owned by the repository.

Additional workflow hygiene checks should include:

```text
ShellCheck
actionlint
GitHub Actions hardening validation
```

GitHub Action dependencies must be pinned to immutable commit SHAs in the final implementation rather than floating major-version tags.

## Gate 2 — Static security

Recommended baseline:

```text
secret scanning          : Gitleaks
SAST                     : GitHub CodeQL for Python and JavaScript
Python dependencies      : pip-audit
Node dependencies        : npm audit / equivalent policy gate
workflow hardening       : zizmor
Dockerfile lint/security : Hadolint
```

Security reports that support SARIF should be uploaded to GitHub code scanning where the repository permissions permit it.

High/critical findings block admission unless an explicit KAORI governance exception exists.

## Gate 3 — Functional and integration tests

Repository authority:

```bash
bash scripts/quality_gate.sh --tests
```

The test stack uses isolated containers:

```text
CI network
├── KAORI CI toolchain
├── postgres:5432
└── redis:6379
```

No PostgreSQL or Redis host-port publication is required.

CI values use service DNS rather than `127.0.0.1`:

```text
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/kaori_test
TEST_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/kaori_test
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/3
```

## Gate 4 — Frontend reproducibility

Repository authority:

```bash
bash scripts/quality_gate.sh --frontend
```

The gate must prove that vendored frontend dependencies and generated frontend assets reproduce the committed canonical state.

## Gate 5 — Production image validation

Every `kaori/working` change builds the production Docker target.

The branch image is a **validation artifact only**:

```text
kaori:ci-<commit-sha>
```

It is not pushed to Docker Hub and is not a release candidate.

Validation includes:

```text
production Docker build
container startup
health/readiness
container vulnerability scan
runtime smoke
```

Recommended container scanner:

```text
Trivy
```

The local validation image is removed during CI cleanup.

## Gate 6 — Runtime security / DAST

DAST runs against an ephemeral CI environment, never against production.

Initial runtime topology:

```text
isolated CI network

postgres
   │
redis
   │
KAORI validation image
   │
OWASP ZAP
```

Initial scanner:

```text
OWASP ZAP
```

A baseline unauthenticated policy can be implemented first. Authenticated application flows may be added later once the test identity and anti-CSRF/login mechanics are explicitly modeled.

The environment is destroyed after every run.

## Gate 7 — Admission result

A final required check summarizes the preceding gates.

Conceptual result:

```text
KAORI CI Admission
```

It is green only when all required CI jobs are green.

This is the required branch-protection signal for `main`.

---

# Planned CI Container Layout

The preferred implementation does not install application runtimes onto the host runner.

Planned repository structure:

```text
.github/
├── ci/
│   ├── Dockerfile
│   └── compose.yml
└── workflows/
    ├── quality.yml
    └── release.yml
```

The CI Dockerfile owns the reproducible Python 3.12, Node.js 22, npm, build tooling, and native PDF/runtime libraries needed by KAORI gates.

The Compose project owns the test network and transient services.

Use a unique project name per Actions run:

```text
kaori-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}
```

This prevents network, volume, and container-name collisions if additional runners are introduced later.

Local Dev Container Compose and CI Compose remain separate concerns.

---

# Planned `quality.yml`

The final YAML will preserve existing KAORI gate entry points and move execution to `kaori-ci`.

The following is a **design skeleton**, not the final executable workflow:

```yaml
name: KAORI CI

on:
  workflow_call:
  push:
    branches:
      - kaori/working
      - main
  pull_request:
    branches:
      - main

permissions:
  contents: read
  security-events: write

concurrency:
  group: kaori-ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}

jobs:
  static-quality:
    name: Static, Architecture, Governance
    runs-on: [self-hosted, linux, x64, kaori-ci]
    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_COMMIT_SHA>

      - name: Build CI toolchain
        run: docker compose -f .github/ci/compose.yml build ci

      - name: Run KAORI static gate
        run: >
          docker compose -f .github/ci/compose.yml
          run --rm ci bash scripts/quality_gate.sh --static

  static-security:
    name: SAST, Secrets, Dependencies
    needs: static-quality
    runs-on: [self-hosted, linux, x64, kaori-ci]
    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_COMMIT_SHA>

      # Gitleaks
      # CodeQL / SAST
      # pip-audit
      # npm dependency audit
      # actionlint / zizmor
      # Hadolint

  functional-tests:
    name: Functional and Integration
    needs: static-security
    runs-on: [self-hosted, linux, x64, kaori-ci]
    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_COMMIT_SHA>

      - name: Start test services
        run: >
          docker compose -f .github/ci/compose.yml
          up -d postgres redis

      - name: Run KAORI tests
        run: >
          docker compose -f .github/ci/compose.yml
          run --rm ci bash scripts/quality_gate.sh --tests

  frontend:
    name: Frontend Reproducibility
    needs: functional-tests
    runs-on: [self-hosted, linux, x64, kaori-ci]
    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_COMMIT_SHA>

      - name: Run frontend gate
        run: >
          docker compose -f .github/ci/compose.yml
          run --rm ci bash scripts/quality_gate.sh --frontend

  production-runtime:
    name: Production Image, Runtime, DAST
    needs: frontend
    runs-on: [self-hosted, linux, x64, kaori-ci]
    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_COMMIT_SHA>

      - name: Build validation image
        run: >
          docker build
          --target production
          --tag kaori:ci-${GITHUB_SHA}
          .

      # Trivy scan
      # ephemeral production runtime
      # health/readiness
      # E2E smoke
      # OWASP ZAP DAST

      - name: Cleanup
        if: always()
        run: >
          docker compose -f .github/ci/compose.yml
          down --volumes --remove-orphans

  admission:
    name: KAORI CI Admission
    if: always()
    needs:
      - static-quality
      - static-security
      - functional-tests
      - frontend
      - production-runtime
    runs-on: [self-hosted, linux, x64, kaori-ci]
    steps:
      - name: Assert required gates
        run: |
          # Final implementation will fail unless every required job succeeded.
          true
```

The final implementation must use a deterministic admission assertion rather than the placeholder shown above.

---

# Main Branch Governance

`main` is governed by repository rules.

Recommended rules:

```text
pull request required
required status check: KAORI CI Admission
merge commits allowed
squash merge disabled for normal KAORI flow
rebase merge disabled for normal KAORI flow
force push blocked
branch deletion blocked
```

`kaori/working` should also block force-push and deletion while allowing authorized normal pushes.

The working branch must survive PR merges.

---

# Changelog and Release Preparation

`CHANGELOG.md` remains the source of truth for operator-visible release changes.

Normal development records applicable entries under:

```text
## [Unreleased]
```

When the user says:

```text
release 2.4.0
```

the assistant creates a dedicated release-preparation branch:

```text
release/v2.4.0
```

The release-preparation PR contains only approved release metadata/evidence changes, including:

```text
APP_VERSION canonical update
CHANGELOG [Unreleased] → [2.4.0] - YYYY-MM-DD
docs/releases/KAORI_2_4_0.md
release evidence adjustments required by governance
```

The release PR runs the normal full PR CI plus release-governance validation.

The user explicitly approves the release-preparation merge.

---

# Release Trigger

Release publication is **manual**.

The GitHub workflow is launched using:

```text
Release
```

with one required input:

```text
version = 2.4.0
```

The workflow must be dispatched from `main`.

The workflow does not infer the release version from commit messages.

The workflow does not automatically edit `CHANGELOG.md` or `APP_VERSION`.

Those files must already have been reviewed and merged through the release-preparation PR.

---

# Release Preflight

Before privileged registry credentials are available, the release workflow validates:

```text
dispatch ref is main
input matches strict SemVer
exact dispatch SHA is locked
APP_VERSION matches input
CHANGELOG contains the dated release section
docs/releases/KAORI_X_Y_Z.md exists
Git tag vX.Y.Z does not conflict
release governance verifier passes
canonical final release verifier passes
full reusable quality workflow passes
```

Canonical final release command remains:

```bash
python scripts/verify_final_release.py --all --runtime
```

A preflight failure creates:

```text
no SemVer image
no Git tag
no GitHub Release
```

---

# Build Once, Verify, Promote

## Working branch

Working CI builds a local validation image and discards it.

It is never promoted to release.

## Release candidate

After release-preparation metadata is merged and release preflight passes, the release job enters:

```text
environment: release
```

The Environment approval boundary exposes Docker Hub credentials only to the privileged release job.

The job locks:

```text
RELEASE_VERSION = X.Y.Z
RELEASE_SHA     = exact workflow-dispatch Git SHA
RELEASE_DATE    = UTC build timestamp
```

The production image is built **once** from that exact SHA and initially pushed using a commit tag:

```text
<image>:sha-<commit>
```

The registry digest is captured:

```text
sha256:<digest>
```

No subsequent release stage rebuilds the image.

## Candidate validation

The actual release candidate image is validated by digest.

Required release-candidate evidence:

```text
container vulnerability scan
SBOM
build provenance
image signing
runtime startup
health/readiness
E2E smoke
DAST
fresh-database migration validation
supported previous-release database upgrade validation
final release governance
```

If candidate validation fails:

```text
no SemVer promotion
no GitHub Release
```

The commit-tagged candidate may remain as non-release traceability evidence until retention cleanup.

## Promotion

After all candidate gates succeed:

```text
<image>:sha-<commit>
<image>:X.Y.Z
<image>:X.Y
```

must all resolve to:

```text
sha256:<same digest>
```

Promotion is a manifest/digest retag operation, not a Docker rebuild.

The deployment contract should prefer:

```text
<image>@sha256:<digest>
```

for immutable production rollout and rollback.

---

# Release Manifest

Every release produces:

```text
kaori-release-manifest.json
```

Conceptual content:

```json
{
  "version": "2.4.0",
  "git_tag": "v2.4.0",
  "git_sha": "987654321abcdef",
  "image": "<namespace>/kaori:2.4.0",
  "digest": "sha256:...",
  "build_date": "2026-08-26T00:00:00Z",
  "sbom": true,
  "provenance": true,
  "signed": true
}
```

The manifest is attached to the GitHub Release.

---

# Planned `release.yml`

The following is a **design skeleton**, not the final executable workflow:

```yaml
name: Release KAORI

on:
  workflow_dispatch:
    inputs:
      version:
        description: Semantic Version, for example 2.4.0
        required: true
        type: string

permissions:
  contents: read

concurrency:
  group: kaori-release
  cancel-in-progress: false

jobs:
  quality:
    uses: ./.github/workflows/quality.yml

  preflight:
    name: Release Preflight
    needs: quality
    runs-on: [self-hosted, linux, x64, kaori-ci]
    outputs:
      release_sha: ${{ steps.release.outputs.sha }}
      release_version: ${{ steps.release.outputs.version }}
    steps:
      - name: Checkout exact dispatch commit
        uses: actions/checkout@<PINNED_COMMIT_SHA>
        with:
          ref: ${{ github.sha }}
          fetch-depth: 0

      - name: Validate release identity
        id: release
        shell: bash
        run: |
          # Validate refs/heads/main.
          # Validate strict SemVer.
          # Validate APP_VERSION.
          # Validate CHANGELOG release section.
          # Validate docs/releases/KAORI_X_Y_Z.md.
          # Validate vX.Y.Z tag conflict rules.
          # Emit exact release SHA and version.

      - name: Run canonical final release gate
        run: >
          docker compose -f .github/ci/compose.yml
          run --rm ci
          python scripts/verify_final_release.py --all --runtime

  publish:
    name: Build, Verify, Promote, Release
    needs: preflight

    environment:
      name: release

    runs-on: [self-hosted, linux, x64, kaori-ci]

    permissions:
      contents: write
      id-token: write
      security-events: write

    steps:
      - name: Checkout exact approved SHA
        uses: actions/checkout@<PINNED_COMMIT_SHA>
        with:
          ref: ${{ needs.preflight.outputs.release_sha }}
          fetch-depth: 0

      - name: Log in to Docker Hub
        # Final implementation uses the pinned official Docker login action.
        # Credentials:
        #   secrets.DOCKERHUB_USERNAME
        #   secrets.DOCKERHUB_TOKEN

      - name: Build and push candidate exactly once
        # Build production target.
        # Inject APP_VERSION / APP_BUILD_SHA / APP_BUILD_DATE.
        # Push only sha-<commit> initially.
        # Enable SBOM and provenance.
        # Capture immutable registry digest.

      - name: Scan exact candidate digest
        # Trivy high/critical policy.

      - name: Validate exact candidate runtime
        # Pull/run the candidate by digest.
        # PostgreSQL + Redis isolated services.
        # health/readiness + E2E + DAST.
        # migration upgrade evidence.

      - name: Sign candidate digest
        # Cosign keyless using GitHub OIDC.

      - name: Create annotated release tag
        # Create vX.Y.Z at the exact release SHA.
        # If it already exists at the same SHA during a safe retry, continue.
        # If it points elsewhere, fail closed.

      - name: Promote same digest
        # sha-<commit> → X.Y.Z and X.Y
        # No rebuild.

      - name: Verify promoted tags
        # Assert every release tag resolves to the captured digest.

      - name: Generate release manifest
        # kaori-release-manifest.json

      - name: Publish GitHub Release
        # Release title: KAORI X.Y.Z
        # Release body from approved release evidence.
        # Attach kaori-release-manifest.json.
```

---

# Publication Failure and Retry Contract

Publication must be idempotent.

A retry may continue an incomplete release only if all existing evidence matches the exact approved release identity.

Examples:

```text
existing v2.4.0 tag at expected SHA
    → safe to continue

existing v2.4.0 tag at different SHA
    → hard failure

existing 2.4.0 image tag at expected digest
    → safe to continue

existing 2.4.0 image tag at different digest
    → hard failure

existing GitHub Release with conflicting identity
    → hard failure
```

Never overwrite or move an already published release identity to conceal a failed release.

A real source correction uses the next Semantic Version, for example:

```text
2.4.0 → 2.4.1
```

---

# Security Boundary

Working/PR CI:

```text
no Docker Hub release credentials
no release publication permission
no persistent signing key
```

Release job:

```text
GitHub Environment: release
required human approval
Docker Hub token only where explicitly referenced
contents: write only for publication job
id-token: write for keyless signing
```

Secrets must never be printed into logs, embedded into images, included in SARIF/reports, or written to release artifacts.

Third-party Actions must be reviewed and pinned to immutable commit SHAs.

---

# Artifact Retention

Recommended baseline:

```text
working/PR diagnostic artifacts : short retention
main CI evidence                : medium retention
release manifest                : GitHub Release attachment
release image                   : immutable Docker Hub digest
SBOM/provenance/signature       : attached to or associated with the immutable image digest
```

Candidate commit tags may have a defined cleanup policy later, but automated destructive registry cleanup is not part of the initial implementation.

---

# Initial Rollout Order

1. Prepare the self-hosted runner host.
2. Register `kaori-ci-01` and verify `Online / Idle`.
3. Create GitHub Environment `release`.
4. Add only the required Docker Hub secrets/variables once the final workflow names are fixed.
5. Introduce the repository-owned CI Docker/Compose environment.
6. Migrate `quality.yml` to the `kaori-ci` runner.
7. Validate a controlled working-branch CI run.
8. Establish/protect the long-lived `kaori/working` branch.
9. Validate laptop sync and Dev Container review flow.
10. Validate PR integration CI and merge-commit resynchronization.
11. Implement the manual `release.yml`.
12. Test release flow with a non-production trial version/tag policy before the first production release.
13. Only after release publication is stable, design deployment-to-staging/production automation.

---

# Non-Goals for the Initial Rollout

The first rollout does not:

```text
auto-merge PRs
auto-create PRs
infer SemVer from commit messages
publish every working-branch image
use release credentials in branch CI
deploy directly to production
depend on latest image tags
rebuild an image after release validation
skip full CI for small changes
```

---

# Canonical Lifecycle Summary

```text
                           DAILY DEVELOPMENT

                                 main
                                  │
                                  ▼
                           kaori/working
                                  │
                         assistant implements
                                  │
                                  ▼
                         FULL WORKING CI
                                  │
                                GREEN
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
                 GitHub                  laptop sync
                                               │
                                               ▼
                                         Dev Container
                                               │
                                               ▼
                                         user validates
                                               │
                                          "lanjut PR"
                                               │
                                               ▼
                                           PR → main
                                               │
                                               ▼
                                      merge-result full CI
                                               │
                                             GREEN
                                               │
                                           user "merge"
                                               │
                                               ▼
                                         merge commit
                                               │
                                               ▼
                                              main
                                               │
                                               ▼
                                  fast-forward kaori/working


                              RELEASE LIFECYCLE

                                              main
                                               │
                                      user: release X.Y.Z
                                               │
                                               ▼
                                      release/vX.Y.Z
                                               │
                                    release metadata PR
                                               │
                                      full CI + governance
                                               │
                                             GREEN
                                               │
                                         user approves
                                               │
                                               ▼
                                              main
                                               │
                                      manual Release X.Y.Z
                                               │
                                               ▼
                                      exact SHA locked
                                               │
                                      full release preflight
                                               │
                                               ▼
                                   GitHub Environment: release
                                               │
                                      required human approval
                                               │
                                               ▼
                                      BUILD EXACTLY ONCE
                                               │
                                               ▼
                                  image:sha-<commit> + digest
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                        scan                 SBOM              provenance
                          │
                        signing
                          │
                   runtime / E2E / DAST
                          │
                  migration upgrade evidence
                          │
                    FINAL RELEASE GATE
                          │
                        GREEN
                          │
                    annotated vX.Y.Z
                          │
                  PROMOTE SAME DIGEST
                          │
                 ┌────────┼─────────┐
                 ▼        ▼         ▼
               X.Y.Z     X.Y   sha-<commit>
                 └────────┼─────────┘
                          ▼
                    same sha256
                          │
                          ▼
                kaori-release-manifest.json
                          │
                          ▼
                   GitHub Release X.Y.Z
                          │
                          ▼
                     READY TO DEPLOY
```
