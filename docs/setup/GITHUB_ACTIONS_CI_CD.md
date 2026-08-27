# KAORI GitHub Actions CI/CD

## Status

**CURRENT — GitHub Organization Free / private repository.**

This document is the canonical CI and release-publication contract for KAORI. It complements `docs/setup/GITHUB_ACTIONS_SELF_HOSTED_RUNNER.md` and the existing release governance in `docs/deployment/RELEASE_GOVERNANCE.md`.

The current implementation stops at a verified, signed, immutable application image and GitHub Release. Application deployment is intentionally outside the current scope, but every release output is designed so a later CD workflow can deploy the exact approved image digest without rebuilding it.

The implementation preserves the repository's existing authorities:

```bash
bash scripts/quality_gate.sh --static
bash scripts/quality_gate.sh --tests
bash scripts/quality_gate.sh --frontend
python scripts/verify_final_release.py --all --runtime
```

GitHub Actions orchestrates those gates. It must not weaken, skip, or silently replace them.

---

## Current Platform Boundary

KAORI currently assumes:

```text
Repository owner : GitHub Organization
Repository       : private
GitHub plan       : Free
Runner            : self-hosted Linux
Runner family     : kaori-ci
Runner instance   : kaori-ci-01
Registry          : Docker Hub
Production CD     : not implemented yet
```

The self-hosted runner selector is:

```yaml
runs-on:
  - self-hosted
  - linux
  - x64
  - kaori-ci
```

The runner VM is an executor only. Python, Node.js, PostgreSQL, Redis, security scanners, and application test dependencies belong to repository-owned containers.

---

# Source-Control Contract

## Long-lived working branch

Daily work uses one stable branch:

```text
kaori/working
```

The normal lifecycle is:

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
              FULL CI
                   │
                 GREEN
                   │
                   ▼
          developer syncs laptop
                   │
                   ▼
            KAORI Dev Container
                   │
                   ▼
          runtime + visual review
                   │
             "lanjut PR"
                   │
                   ▼
                PR → main
                   │
              FULL PR CI
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

Exceptional isolated work may use:

```text
kaori/hotfix/<slug>
release/vX.Y.Z
```

The developer should not have to switch local branches for normal work. An exceptional branch switch must be called out explicitly.

## Merge strategy

Normal PRs from `kaori/working` use **merge commits**.

Do not use squash or rebase merge for this long-lived branch because `kaori/working` must remain fast-forwardable to the resulting `main` history.

After merge:

```bash
git fetch origin
git switch kaori/working
git merge --ff-only origin/main
git push origin kaori/working
```

## Human acceptance boundary

Machine approval and human acceptance are separate gates:

```text
GitHub Actions green
        ≠
permission to merge
```

The assistant may create a PR only after local Dev Container review is accepted. The PR may be merged only after the user explicitly authorizes the merge.

No workflow auto-creates PRs or auto-merges them.

---

# Full-CI Policy

Every change runs the full CI cycle during the initial baseline, including small changes such as:

```text
wording
CSS
Jinja templates
documentation
one-line Python changes
workflow changes
migration changes
```

The baseline intentionally does not use broad `paths-ignore` shortcuts.

This policy can be optimized later only after enough historical CI evidence exists to prove that a fast path does not create verification blind spots.

A full CI cycle does **not** mean release publication. Working/PR/main CI never:

```text
logs into Docker Hub with release credentials
pushes SemVer release tags
creates a Git tag
creates a GitHub Release
deploys to production
```

---

# `quality.yml`

## Triggers

The CI workflow responds to:

```yaml
on:
  workflow_call:
  workflow_dispatch:
  push:
    branches:
      - kaori/working
      - main
      - "release/**"
  pull_request:
    branches:
      - main
    types:
      - opened
      - synchronize
      - reopened
      - ready_for_review
```

The trigger meanings are:

| Trigger | Purpose |
| --- | --- |
| push `kaori/working` | validate the exact daily working commit |
| push `release/**` | validate release-preparation metadata plus application state |
| PR → `main` | validate the prospective integration result |
| push `main` | validate the exact canonical merged SHA |
| `workflow_call` | reusable full CI from release orchestration |
| `workflow_dispatch` | manual diagnostic rerun without publication |

Pull requests from forks are not admitted onto the trusted self-hosted Docker runner. This avoids executing untrusted fork code on a runner account with Docker privileges.

## Concurrency

Obsolete working/PR runs may be cancelled when a newer commit supersedes them. Canonical `main` and release execution must not be cancelled merely because a later commit appears.

## Job sequence

The required admission order is:

```text
static-quality
    ↓
static-security
    ↓
functional-tests
    ↓
frontend
    ↓
production-runtime
    ↓
admission
```

The sequence is intentionally fail-fast from cheaper checks to more expensive runtime checks.

---

## Job: Static, Architecture, and Governance

### Purpose

Prove the checked-out source satisfies the existing KAORI structural, formatting, migration, architectural, and governance contracts.

### Steps

```text
checkout full history
    ↓
build reproducible CI toolchain
    ↓
run scripts/quality_gate.sh --static
```

The existing gate owns Ruff, djLint, Pyright, KAORI verifier scripts, migration checks, architecture checks, UI contracts, code-health checks, and contract/migration tests already defined by the repository.

A failure blocks all more expensive downstream jobs.

---

## Job: Secrets, SAST, Dependencies, and Workflow Security

### Purpose

Provide security coverage that works on a private Organization Free repository without depending on paid GitHub security products.

### CURRENT toolset

```text
Gitleaks     secret detection
Bandit       Python SAST
Semgrep      local high-confidence SAST rules
pip-audit    Python dependency vulnerabilities
npm audit    Node dependency vulnerabilities
actionlint   GitHub Actions syntax/semantic lint
Zizmor       GitHub Actions security analysis
ShellCheck   CI shell correctness
Hadolint     Dockerfile lint/security
```

Semgrep uses the committed `.github/ci/semgrep.yml` configuration. It must not download an uncontrolled `auto` ruleset at runtime.

Required findings fail closed. Accepted risks require a reviewed, explicit suppression or governance exception; do not use blanket `|| true` or `continue-on-error` to manufacture a green result.

Diagnostic reports are short-retention Actions artifacts and must not contain credentials.

---

## Job: Functional and Integration Tests

### Purpose

Run the canonical KAORI behavioral test suite in an isolated service network.

### Service topology

```text
CI Compose project
├── ci toolchain
├── postgres:5432
└── redis:6379
```

PostgreSQL and Redis do not publish host ports.

The CI contract uses service DNS:

```text
TEST_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/kaori_test
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/kaori_test
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/3
```

The canonical command is:

```bash
bash scripts/quality_gate.sh --tests
```

Cleanup runs even when tests fail.

---

## Job: Frontend Reproducibility

### Purpose

Prove `package-lock.json`, vendored assets, Tailwind output, frontend formatting, and committed frontend assets reproduce the expected canonical state.

Command:

```bash
bash scripts/quality_gate.sh --frontend
```

This is intentionally independent from the local watch process used by the Dev Container.

---

## Job: Production Image, Container Security, Runtime, and DAST

### Purpose

Validate the actual production Docker target, not only the source tree.

### Steps

```text
build production target
        ↓
kaori:ci-<full-sha>
        ↓
Trivy HIGH/CRITICAL scan
        ↓
fresh PostgreSQL migration
        ↓
start exact production image
        ↓
start Reports worker from exact image
        ↓
HTTP readiness
        ↓
Reports worker readiness
        ↓
OWASP ZAP baseline/passive scan
        ↓
collect diagnostics
        ↓
remove transient runtime/image
```

The validation image remains local to the runner and is not pushed to Docker Hub.

### DAST policy

Working/PR/main CI always includes the DAST family, but uses the bounded ZAP baseline/passive scan. Full active scanning is reserved for the release candidate.

DAST targets only an ephemeral isolated KAORI runtime. It never targets production.

---

## Job: KAORI CI Admission

This final status aggregates all required predecessor results.

It succeeds only when every required job reports `success`.

Conceptually:

```text
static-quality     success
static-security    success
functional-tests   success
frontend           success
production-runtime success
        │
        ▼
KAORI CI Admission = success
```

A failure, cancellation, or unexpected skip in a required predecessor fails admission.

When paid private branch protection becomes available, `KAORI CI Admission` becomes the required server-side status check for `main`.

---

# CI Toolchain and Compose Isolation

Repository-owned CI infrastructure lives under:

```text
.github/ci/
├── Dockerfile
├── compose.yml
├── requirements-security.txt
├── semgrep.yml
├── run-security-static.sh
├── run-runtime-validation.sh
├── run-zap-baseline.sh
├── run-zap-full.sh
├── run-release-candidate.sh
└── release-lib.sh
```

Pinned baseline tools include:

```text
Python       3.12
Node.js      22
PostgreSQL   17
Redis        8
Gitleaks     8.30.1
Bandit       1.9.4
pip-audit    2.10.1
Semgrep      1.174.0
actionlint   1.7.12
Zizmor      1.29.0
Hadolint     2.15.1
Trivy        0.74.0
OWASP ZAP    2.17.0
Cosign       3.1.3
```

The CI toolchain downloads standalone binaries from official upstream releases and validates provided checksums before installation.

Use a unique Compose project name per workflow run/attempt so future additional runners do not collide on networks, volumes, or container names.

---

# Release Preparation

`CHANGELOG.md` remains the release-history source of truth.

Operator-visible changes should be accumulated under:

```text
## [Unreleased]
```

When the user requests a release, for example:

```text
release 2.4.0
```

a dedicated branch is prepared:

```text
release/v2.4.0
```

The release-preparation PR finalizes:

```text
canonical APP_VERSION = 2.4.0
KAORI_IMAGE=${DOCKERHUB_IMAGE}:v2.4.0
CHANGELOG [Unreleased] entries → dated [2.4.0] section
docs/releases/KAORI_2_4_0.md
release-governance evidence required by existing verifiers
```

The release-preparation PR still runs the full CI cycle and remains subject to explicit user approval before merge.

---

# `release-image.yml`

## Trigger

Release publication is manual:

```yaml
on:
  workflow_dispatch:
    inputs:
      version:
        description: Semantic Version, for example 2.4.0
        required: true
        type: string
```

The user supplies only the version. Image name, SHA, changelog path, release-note path, and tags are derived from repository state.

The workflow must be dispatched from `main`.

---

## Release stage 1: full fresh CI

The release workflow reuses `quality.yml`.

A previously green PR is not accepted as sufficient release evidence. The exact release-dispatch SHA receives a fresh full CI result.

---

## Release stage 2: preflight without publication credentials

Preflight validates:

```text
workflow was dispatched from main
version is strict MAJOR.MINOR.PATCH
release SHA is exact and locked
APP_VERSION matches requested version
KAORI_IMAGE=${DOCKERHUB_IMAGE}:vX.Y.Z
CHANGELOG contains dated release section
matching docs/releases/KAORI_X_Y_Z.md exists
Git tag conflict rules are satisfied
verify_release_governance.py passes
verify_final_release.py --all --runtime passes
Reports worker is live for runtime release verification
```

If preflight fails:

```text
no Docker Hub publication
no SemVer registry tag
no Git tag
no GitHub Release
```

---

# CURRENT — GitHub Organization Free Release Boundary

A private repository under GitHub Organization Free cannot use the paid private-environment protection model we ultimately want. Therefore the current release boundary is implemented through process isolation and job-level least privilege.

Repository Actions secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

Repository Actions variable:

```text
DOCKERHUB_IMAGE
```

`DOCKERHUB_TOKEN` must be a scoped Docker Hub access token, not the Docker Hub account password.

Only the release publication job references these credentials. `quality.yml` does not reference them.

The built-in GitHub token is used for Git tag/GitHub Release publication with `contents: write` granted only to the release publication job.

Keyless signing uses GitHub OIDC with `id-token: write`; no long-lived Cosign private key is stored.

This is a logical release boundary, not a protected GitHub Environment boundary.

---

# Build Once → Verify → Promote Same Digest

## Working CI

Working CI builds:

```text
kaori:ci-<sha>
```

It is scanned, run, DAST-tested, and removed locally. It is not a release artifact.

## Release candidate

After release metadata is approved and preflight passes, the exact locked SHA is built once and pushed initially as:

```text
${DOCKERHUB_IMAGE}:sha-<short-sha>
```

BuildKit records:

```text
org.opencontainers.image.version
org.opencontainers.image.revision
org.opencontainers.image.created
SBOM
provenance
```

The registry returns the immutable digest:

```text
sha256:<digest>
```

After that point no release stage may rebuild the application image.

## Exact candidate validation

Every release-candidate validation targets:

```text
${DOCKERHUB_IMAGE}@sha256:<digest>
```

Required evidence:

```text
OCI identity labels
Trivy HIGH/CRITICAL scan
fresh database migration
actual production runtime startup
actual production Reports worker readiness
previous supported release DB → current migration path
full active OWASP ZAP scan
Cosign keyless signature
signature verification
```

If any required evidence fails, there is no SemVer promotion and no GitHub Release.

## Promotion

After candidate verification:

```text
:vX.Y.Z
:vX.Y
:sha-<short-sha>
```

must all resolve to the same captured digest.

Promotion is performed with registry manifest/digest operations. It is not a new `docker build`.

The `v` prefix is retained because current KAORI release governance expects the production image example to use `:v<APP_VERSION>`.

---

# Release Failure and Retry Contract

Release publication is idempotent and fails closed.

```text
candidate sha tag absent
→ build once

candidate sha tag exists with matching OCI version/SHA labels
→ reuse exact candidate

candidate sha tag exists with conflicting identity
→ hard fail

vX.Y.Z Git tag absent
→ create annotated tag after candidate verification

vX.Y.Z Git tag exists at same SHA
→ safe retry

vX.Y.Z Git tag exists at different SHA
→ hard fail

vX.Y.Z registry tag absent
→ promote

vX.Y.Z registry tag exists at same digest
→ safe retry

vX.Y.Z registry tag exists at different digest
→ hard fail
```

Never move or overwrite an already published release identity to hide a failure. A real source correction uses the next SemVer release, for example `2.4.1`.

---

# Release Manifest

Every successful release creates:

```text
kaori-release-manifest.json
```

Example:

```json
{
  "version": "2.4.0",
  "git_tag": "v2.4.0",
  "git_sha": "987654321abcdef987654321abcdef987654321a",
  "image": "namespace/kaori:v2.4.0",
  "immutable_image": "namespace/kaori@sha256:...",
  "digest": "sha256:...",
  "promoted_tags": [
    "v2.4.0",
    "v2.4",
    "sha-987654321abc"
  ],
  "build_date": "2026-08-26T00:00:00Z",
  "sbom": true,
  "provenance": true,
  "signed": true
}
```

The manifest must never include credentials, connection strings, internal endpoints, or secret values.

It is attached to the GitHub Release and later becomes the input contract for CD deployment.

---

# GitHub Release

The final publication step creates:

```text
GitHub Release: KAORI X.Y.Z
Git tag       : vX.Y.Z
Docker image  : ${DOCKERHUB_IMAGE}:vX.Y.Z
Digest        : sha256:<digest>
```

Release notes are derived from the reviewed release evidence already committed to the repository, not from an uncontrolled commit-message dump.

A release is considered ready to deploy only after image promotion, digest verification, signing, manifest generation, and GitHub Release publication succeed.

---

# GitHub Organization Free Governance

The current Free/private baseline cannot enforce the full desired private-repository ruleset on the server side.

Therefore current governance is procedural plus CI evidence:

```text
normal work goes through kaori/working
full CI must be green
local Dev Container review is required
PR is created only after explicit approval
merge occurs only after explicit approval
no normal direct-push workflow to main
```

CI can detect or report governance drift after an event, but Free-plan CI cannot retroactively prevent a push that GitHub itself did not protect.

Do not make the repository public merely to obtain Free-plan public-repository rulesets.

---

# PAID ENHANCEMENT — GitHub Team

When the Organization upgrades to GitHub Team, keep the same source-control and CI architecture and add native server-side enforcement.

Recommended `main` ruleset:

```text
require pull request
require KAORI CI Admission
block force push
block deletion
require current integration status before merge
preserve merge-commit workflow
```

Recommended `kaori/working` ruleset:

```text
block force push
block deletion
```

Recommended release-tag ruleset:

```text
target v*
restrict updates
restrict deletion
```

Move Docker Hub publication credentials from repository secrets to the private `release` Environment when the selected paid plan supports the required private-environment secret model.

Restrict release deployment branches to `main`.

No application-image rebuild or CI architecture change is required for this upgrade.

---

# PAID ENHANCEMENT — GitHub Code Security

When GitHub Code Security is licensed for the private repository, add native CodeQL and GitHub code-scanning integration.

Target languages:

```text
Python
JavaScript
```

CodeQL is additive. Existing Bandit/Semgrep/Trivy/KAORI verifiers remain useful defense layers and should not be removed merely because CodeQL becomes available.

Where supported, upload SARIF from compatible scanners into the native Security UI while keeping raw diagnostic artifacts available for failed CI analysis.

---

# PAID ENHANCEMENT — GitHub Secret Protection

When GitHub Secret Protection is licensed, add:

```text
native secret scanning
push protection
secret review/alert workflow
organization security visibility
```

Gitleaks can remain as an independent CI detector and historical scan layer.

---

# PAID ENHANCEMENT — GitHub Enterprise

When stronger enterprise deployment governance is justified, add protected private deployment approval capabilities such as:

```text
required deployment reviewers
prevent self-review where required
stronger environment governance
organization-wide audit/security policy
advanced runner/repository governance
```

The `release` and future `production` boundaries should become GitHub-enforced rather than only process-enforced.

---

# FUTURE CD

Production deployment is not part of the current implementation.

When CD is requested, add a separate deployment workflow rather than extending release image construction into a server-specific script.

The future deployment input is the immutable release manifest/digest:

```text
GitHub Release
      ↓
kaori-release-manifest.json
      ↓
image@sha256:<digest>
      ↓
staging deployment
      ↓
migration + health + smoke
      ↓
approval boundary
      ↓
production deployment
      ↓
post-deploy verification
      ↓
rollback evidence
```

The deployment workflow must never rebuild the image.

Depending on the final application infrastructure, the CD transport may later use Docker Compose over a controlled remote executor, Kubernetes/Helm, or another approved deployment mechanism. That decision is intentionally deferred until the application-server architecture is known.

Future CD should define separate `staging` and `production` governance boundaries and consume the same image digest already verified by the release pipeline.

---

# Required GitHub Repository Configuration — Current Free Baseline

Before enabling release publication, configure repository Actions values:

Secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

Variable:

```text
DOCKERHUB_IMAGE
```

Do not paste these values into workflow files, documentation, issue text, PR comments, or chat transcripts.

The workflow references secret names only.

---

# Rollout Order

Use this order so `main` is not made red by infrastructure that has not been validated yet:

```text
1. bootstrap runner host
2. manually register kaori-ci-01
3. verify runner Online / Idle
4. configure Docker Hub repository secret names and variable
5. apply CI/CD patch locally
6. run local shell/YAML/Compose/toolchain checks
7. push controlled infrastructure commit when explicitly approved
8. establish remote kaori/working
9. run first full working-branch CI
10. remediate any real baseline quality/security findings
11. validate laptop sync + Dev Container review
12. create controlled PR to main
13. validate full PR CI
14. merge only with explicit approval
15. test release workflow with an explicitly approved release-preparation cycle
16. stabilize release publication before designing production CD
```

---

# Failure Policy

```text
static failure
→ do not spend runner time on later gates

security failure
→ block admission; investigate or govern explicitly

functional/frontend failure
→ block image validation

production-image/runtime/DAST failure
→ block admission

PR admission failure
→ do not merge

release preflight failure
→ no publication side effect

candidate build failure
→ no release identity

candidate scan/runtime/migration/DAST failure
→ no SemVer promotion

signing failure
→ no promotion

tag/digest identity conflict
→ hard fail

GitHub Release transient publication failure after valid tag/digest
→ retry idempotently; do not rebuild
```

---

# Canonical Principle

```text
HOST
= executor only

CI CONTAINERS
= deterministic quality/security/runtime environment

REPOSITORY
= application dependency/version/governance source of truth

RELEASE CANDIDATE
= built exactly once from exact approved SHA

PROMOTION
= aliases the same immutable digest

FUTURE DEPLOYMENT
= consumes the same immutable digest without rebuilding
```
