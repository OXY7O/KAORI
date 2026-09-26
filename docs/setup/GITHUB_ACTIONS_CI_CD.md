# KAORI GitHub Actions CI/CD

## Status and authority

**CURRENT — governed staged delivery.**

This document describes the current KAORI Continuous Integration, Continuous Delivery, deployment, promotion, and recovery flow. It complements:

- `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- `docs/deployment/CI_CD_RECOVERY_CONTRACT.md`
- `docs/deployment/RELEASE_GOVERNANCE.md`

Executable authority remains in the repository workflows, deployment tooling, and existing verifiers. Documentation never substitutes for exact-source evidence.

## Delivery model

KAORI uses an issue branch for each work item. The governed lifecycle is:

```text
Issue
  ↓
issue branch
  ↓
Draft PR → kaori/staging
  ↓
Developer Check on exact Draft head
  ↓
Pre-Ready PASS → Ready/frozen candidate
  ↓
Full Admission once on exact frozen head
  ↓
merge commit to kaori/staging
  ↓
exact evidence reuse + Fast Smoke
  ↓
immutable RC + digest-bound supply-chain evidence
  ↓
UAT deployment
  ↓
human acceptance
  ↓
main / stable promotion
  ↓
same immutable digest, no application rebuild
```

The long-lived integration branches are `kaori/staging` and `main`. Work branches are short-lived and issue-scoped.

## Continuous Integration

### Work branch

A `kaori/*` work branch uses the path-aware **Developer Check** workflow while the PR is Draft. It validates the exact PR head without running comprehensive admission on every implementation/fix commit.

A work branch is eligible to become a Ready/frozen candidate only when:

- it is based on or synchronized with the current staging authority;
- Developer Check is green on the exact current Draft head;
- required review discussion is resolved;
- the PR targets `kaori/staging`.

Marking the PR Ready freezes that exact head and starts governed Full Admission. A changed head invalidates the frozen-candidate evidence and should return to Draft for batch repair.

### Final-candidate and staging admission

When the PR is marked Ready, `.github/workflows/quality.yml` runs **Full Admission** on the exact frozen work-branch head when reusable evidence is unavailable. The five comprehensive gates execute as one native matrix with `strategy.fail-fast: true` and `max-parallel: 2`, matching the current single-host capacity ceiling. The Functional Tests critical path is declared in the first scheduling wave so the longest gate starts immediately alongside Static & Governance rather than waiting behind a shorter gate. A decisive matrix failure cancels remaining sibling matrix work instead of waiting for unrelated long-running gates to finish.

After merge to `kaori/staging`, the workflow verifies exact source-tree/authority evidence and transition lineage. The normal staging path reuses the admitted evidence and runs fresh Fast Smoke; staging falls back to a fresh Full Admission only when reuse cannot be proven.

Full Admission owns the integrated evidence set:

- Static & Governance;
- Security;
- Functional Tests;
- Frontend;
- Runtime & DAST;
- CI Admission.

Test execution ownership is intentionally non-overlapping: Static & Governance owns Contract/Migration pytest execution and emits `contract-migration.xml`; Functional Tests owns the remaining non-debug/non-E2E/non-contract/non-migration release suite plus explicit E2E. CI Admission downloads both JUnit artifacts and renders one complete KAORI taxonomy summary before publishing reusable Full Admission evidence.

A green Developer Check does not replace Full Admission. A green Full Admission on the exact frozen Ready head is the comprehensive authority that staging normally reuses.

## Continuous Delivery

Continuous Delivery starts only from a staging SHA whose exact admitted lineage has passed CI Admission, normally through frozen-candidate evidence reuse plus fresh Fast Smoke.

The release-candidate workflow:

1. resolves the exact current `kaori/staging` SHA;
2. requires a successful exact-SHA KAORI CI run;
3. builds the production image once;
4. scans the image;
5. validates production runtime and DAST;
6. publishes an intentional `vX.Y.Z-rc.N` prerelease;
7. records the immutable OCI digest;
8. verifies OCI metadata;
9. generates and verifies SPDX SBOM and SLSA provenance attestations;
10. stores immutable release evidence.

Publication of an immutable RC means the artifact is deployable. It does **not** imply UAT or production acceptance.

## Governed UAT deployment

The UAT/staging-host workflow accepts only an intentional RC bound to the current admitted staging SHA.

Before remote deployment it verifies:

- prerelease identity;
- exact source SHA;
- successful Full Admission;
- immutable staging-image evidence;
- digest-qualified application image.

The server deployment then validates production configuration, infrastructure health, pre-migration backup state, database migration, worker/Beat readiness, immutable application identity, and internal `:5000` readiness.

Public edge publication is a separate infrastructure responsibility and is not required for KAORI application deployment success.

## Continuous Deployment boundary

KAORI does not automatically promote arbitrary source changes to production.

Automatic deployment is permitted only where governance explicitly allows it. Production promotion remains policy-controlled and **human acceptance** gated.

Human acceptance must refer to the exact UAT source SHA and immutable digest. A later source correction requires fresh integration/admission and a new RC lineage.

## Stable promotion

Stable release promotion consumes the explicitly accepted RC and reuses the **same immutable digest**.

Stable promotion must not rebuild application bits. The release workflow verifies:

- accepted RC source lineage;
- accepted RC registry digest;
- OCI labels;
- SBOM and provenance attestations;
- image scan;
- runtime and DAST;
- stable signature;
- promoted tag digest identity.

Stable tags are references to the already-accepted digest, not a new artifact build.

## Release-state transaction boundary

Server release state advances only after the candidate passes runtime verification.

The deployment adapter keeps candidate release identity separate from the active release file until:

- database migration succeeds;
- application services start;
- `deploy/server/verify.sh --restart-check` succeeds;
- internal runtime verification passes.

A failed or cancelled deployment must not silently mark the candidate as accepted.

The candidate state file is discarded unless the deployment transaction reaches the committed state.

## Rollback

Rollback is not an image-only action.

`deploy/server/rollback.sh` requires the complete previous release transaction:

- previous digest-qualified image;
- previous source SHA;
- previous release version;
- reviewed pre-migration database backup.

The rollback sequence is:

```text
validate previous lineage
  ↓
restore reviewed backup
  ↓
redeploy previous immutable image/source/version
  ↓
run normal deployment verification
  ↓
commit recovered release state
```

If the matching image/source/version/backup lineage cannot be proven, rollback must fail closed.

## Roll-forward

Use **roll-forward** when restoring previous data/state would be unsafe, including cases such as:

- irreversible migration or external side effect;
- valid writes would be lost beyond the accepted recovery window;
- previous application code is incompatible with current data;
- prior release lineage or reviewed backup cannot be proven;
- a corrective patch is safer than state restoration.

Roll-forward requires a new governed issue-branch change, fresh Developer Check, a new frozen Ready candidate, Full Admission for that candidate, staging evidence reuse/Fast Smoke, a new immutable RC, deployment verification, and the same human acceptance boundary.

Historical tags, digests, and evidence must remain immutable.

## Rollback versus roll-forward

| Condition | Recovery direction |
| --- | --- |
| Complete previous image/source/version/backup lineage exists and restoration is safe | Rollback may be used |
| Newer schema/data cannot safely run with the previous application | Roll-forward |
| Irreversible external side effects occurred | Roll-forward |
| Accepted writes would be lost outside the approved recovery window | Roll-forward |
| Previous reviewed backup or release lineage cannot be proven | Roll-forward |
| Defect is application-only and the previous complete transaction is safely restorable | Rollback may be used |

Do not perform an image-only rollback as a compromise.

## Failure and retry invariants

- Failed deployment must not advance release state.
- A new source SHA requires fresh admission.
- A published release identity must never be moved to hide a failure.
- Mutable tags are not deployment authority.
- Reusing an immutable candidate is allowed only when source/version/digest identity matches existing evidence.
- Roll-forward always creates fresh admitted lineage.
- Stable promotion always reuses the accepted digest.

## CI security and toolchain

KAORI uses repository-owned, pinned CI tooling on self-hosted Linux runners.

Current security baseline includes:

```text
Gitleaks
Bandit 1.9.4
pip-audit 2.10.1
Semgrep 1.177.0
actionlint
Zizmor 1.29.0
ShellCheck
Hadolint
Trivy
OWASP ZAP
Cosign
```

Semgrep uses the committed repository rules. Required findings fail closed; blanket `|| true`, broad suppression, or gate weakening is not an accepted remediation.

## Supply-chain evidence

RC and stable release evidence is digest-bound.

The release contract records and verifies:

- source SHA;
- candidate/stable version;
- immutable image digest;
- OCI image metadata;
- SPDX SBOM attestation;
- SLSA provenance v1 attestation;
- signature verification;
- stable promoted-tag digest identity.

Boolean placeholders such as `"sbom": true` are not sufficient release evidence.

## CDEvents relationship

Issue #440 tracks CDEvents delivery-lineage standardization.

CDEvents are an **observability** representation of CI, publication, deployment, acceptance, promotion, rollback, and roll-forward transitions. They are **not authorization** and cannot replace workflow/verifier evidence. The pinned vocabulary, identity, retry/idempotency, producer-trust, sensitive-data, and failure contract is `docs/architecture/cdevents-delivery-lineage.md`.

## Canonical workflows

| Purpose | Authority |
| --- | --- |
| Work-branch validation | `.github/workflows/developer-check.yml` |
| Integrated staging admission | `.github/workflows/quality.yml` |
| Immutable RC publication | `.github/workflows/publish-staging-image.yml` |
| Governed UAT deployment | `.github/workflows/deploy-staging-host.yml` |
| Stable promotion | `.github/workflows/release-image.yml` |

## Canonical recovery/runtime tools

- `deploy/server/deploy.sh`
- `deploy/server/release-state.sh`
- `deploy/server/backup.sh`
- `deploy/server/restore.sh`
- `deploy/server/rollback.sh`
- `deploy/server/verify.sh`

## Required quality authorities

The existing quality and release checks remain mandatory:

```bash
bash scripts/quality_gate.sh --static
bash scripts/quality_gate.sh --tests
bash scripts/quality_gate.sh --frontend
python scripts/verify_release_governance.py
python scripts/verify_final_release.py --all --runtime
```

Do not create a parallel pipeline to bypass these authorities.
