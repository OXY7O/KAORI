# KAORI GitHub Actions CI/CD

## Status and authority

**CURRENT — governed staged delivery.**

This document describes the current KAORI Continuous Integration, Continuous Delivery, deployment, promotion, and recovery flow. It complements:

- `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- `docs/deployment/CI_CD_RECOVERY_CONTRACT.md`
- `docs/deployment/RELEASE_GOVERNANCE.md`

Executable authority remains in the repository workflows, deployment tooling, and existing verifiers. Documentation never substitutes for exact-source evidence.

## Operator-facing gate evidence (issue #3941)

**Developer Check is changed-path selected; Full Admission is comprehensive.** A green `Python & Governance` lane reports the actual commands selected by the canonical planner, not a count of all Python functions, test cases or release domains. GitHub Actions **Step Summary** records the command, outcome, elapsed time and the selected route; **the expanded running step log** additionally streams the selected command and verifier stdout, with a 60-second heartbeat for long-running Developer Check commands. an unselected check is **NOT RUN**, never implied PASS. Frontend and focused pytest selectors are reported separately; pytest result counts come from actual executed pytest/JUnit, not static file registration.

In Full Admission, **Static & Governance** publishes every actually executed Foundation, Domain and Engineering verifier as one job summary, with the original command, result, duration and its raw diagnostic-log filename. In the expanded **Run Static & Governance** step, the running verifier name is shown during the existing minute heartbeat, with the exact invoked command at verifier start and a bounded excerpt of standardized PASS lines after success. The full raw log is **not** printed into the live console and remains in the artifact. In expanded **Run Functional Tests**, captured pytest results surface at completion, with a heartbeat during long-running suites; no partial test counts are treated as final. This extra live verbosity is explicitly enabled only by the official CI workflow; ordinary release CLI behavior stays unchanged. Successful static logs are uploaded as a short-retention `full-admission-static-verifiers-*` artifact; failures continue to upload the original Static Diagnostics artifact. The existing Release Surface Coverage registry supplies **REGISTERED** ownership counts for 18 release surfaces; that inventory is neither the count of pytest cases nor a substitute for their execution status. Contract & Migration Safety uses its existing JUnit `contract-migration.xml` and remains independently executable.

The comprehensive gate matrix also reports the actual selected Security, Functional Tests, Frontend and Runtime/DAST step outcomes. In expanded steps, Runtime/DAST visibly reports dependency startup, migration, bounded readiness-probe progress, Reports worker checks and the live ZAP baseline. The staging Fast Smoke lane also reports selected pytest execution and its long-running heartbeat. The CI Admission job exposes selected full-versus-reused lineage, actual JUnit taxonomy extraction and generated source-tree evidence before its final aggregate/commit-status decision. A successful Security gate (including npm dependency audit) publishes its existing JSON scan evidence (no new scan, only retained artifacts); failures can stop before later scanners, so a partially executed script never claims the full tool chain PASS. Functional and E2E counts belong to collected JUnit and the admission taxonomy. Image build, vulnerability scan and runtime/DAST each retain their separate outcome. A **skipped, cancelled, reused or incomplete** gate is never silently counted as fresh PASS.

**Naming policy.** Keep established physical script identities (`verify_*_final_lock.py`, `verify_pre_release_type_safety.py`, contract-test module paths and JUnit names) until all import sites, workflow consumers, baseline authorities, issue history and release-evidence contracts can be migrated together. Operator-facing summaries use meaningful capability/check labels *and expose the exact executable name* rather than performing speculative bulk renames. Preserve the existing quiet, short-PASS general release CLI; the expanded human-readable reports belong to GitHub Actions CI, where operators need evidence discovery.

### Verifier purpose and capability evidence

Full Admission Static & Governance reports each **executed** verifier with a concise purpose/scope, its canonical executable command, outcome, duration, and retained raw diagnostic log. The expanded CI step shows that scope at verifier start. This is presentation-only: it never changes verifier selection, order, exit status, security checks or admission evidence lineage. The general release CLI retains PASS-short/FAIL-detailed output.

**Source Control / GitHub:** The canonical `Integrations` release surface owns `integrations.source_control`, `source_control_bp`, `github_source_bp` and `github_uat_bp`. Integration provider/navigation/final-lock verifiers protect common integration architecture and UI. They do **not** individually attest GitHub webhook signature handling, installation-scoped repository inventory, background synchronization, scoped authorization or UAT readiness. Such behavior is evaluated by actual executed functional/security/contract tests and eventually hosted UAT, with separate results and evidence. A registry `REGISTERED` line only establishes ownership. A green static lock alone is never GitHub functional acceptance.

When a new domain/provider is added, update the existing taxonomy, release-surface registry, contract tests and documentation together. Add purpose text to the existing presentation mapping only where the generic verifier label is ambiguous. Do not create duplicate static gates, infer universal test coverage from the explicit permanent test-file baseline, or rename physical `verify_*` scripts without migrating their consumers and historical contracts.

## Release Candidate expanded-step execution evidence

After successful exact staging Full Admission, the existing `Release Candidate` workflow shows live, operator-readable phase start and actual completion within each expanded job step: accepted staging SHA and quality run, production image build, Trivy HIGH/CRITICAL scan, isolated runtime/DAST validation, immutable Git tag reservation, registry push/pull and digest capture, OCI metadata verification, SPDX/SLSA attestations, and GitHub prerelease publication. The native GitHub step conclusion remains the authoritative success/failure signal, not printed preview labels. Never infer UAT host deployment or human acceptance from RC publication; keep immutable artifact and attestation evidence as the verifiable source of truth. Console status messages contain only approved release identities and phase labels, not registry secrets or OIDC tokens.

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
Developer Check on exact Ready head
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

**Temporary DevContainer review workbench (#2227).** The existing `kaori/review/staging-uat` branch holds separately issue-owned exploratory UAT work; it does not add a third integration, CI-admission or release authority. Official `.github/workflows/developer-check.yml` only handles PRs targeting `kaori/staging`; a review-target merge, browser screenshot or source audit does not imply any mandatory security/Full Admission gate PASS. Synchronize accepted `kaori/staging` commits **into** the review branch with non-force, expected-head fast-forward when it is an ancestor, or an explicitly reviewed merge if it diverges. Never bulk-promote the holding branch into staging: return individually accepted changes through normal staging-target issue PRs and exact-head gates. DevContainer UAT only covers the actual recorded environment/provider scenarios; see `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` and #2227 for evidence boundaries.

For the **single operator-accepted committed source snapshot** recorded by #1710 on 2026-10-26 (`1a9a708f044e06d584f1882e83877812dcfbac88`), an independent issue-linked Draft admission PR #3399 copies that exact committed source without updating the moving review branch or absorbing the 15 still-open review-target PR heads. This is a specifically recorded acceptance decision under the **existing** official staging PR gates, not permission for bulk promotion of future review work. Each gate remediation is issue-scoped and invalidates old exact-head evidence; server UAT, migration/backup, security and human acceptance stay independently required. The controlling interpretation and source boundary are documented in `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` (#3407).

## Continuous Integration

### Work branch

A `kaori/*` work branch uses the path-aware **Developer Check** workflow for Draft development and independent exact-head verification on Ready. Draft validation remains targeted; it produces a bounded route-identity artifact but this artifact is **not PASS evidence on its own**. If the Ready event has the same trusted live PR, head/base SHA, source tree, canonical plan, authority fingerprint and toolchain key, a completed successful Draft workflow and every required GitHub job conclusion must be verified before the Ready aggregate can reuse those results. Evidence is valid for at most two hours. Missing/failed/stale/changed evidence, API unavailability, or suspicious job state falls back to ordinary fresh Ready lanes. Regardless of reuse, Ready Full Admission runs **only after** exact-head Developer Check aggregate PASS, with its complete Security, Functional, Static, Frontend, Runtime/DAST and CI Admission coverage. A separate lightweight **Ready Admission Guard** fails the workflow unless both the exact-head Developer Check aggregate and the mandatory Full Admission job actually finish SUCCESS; a skipped Full Admission is never accepted as a green Ready run.

Developer Check resolves changed paths once, prepares one deterministic shared CI toolchain, and runs the heavy `kaori-ci` lanes **sequentially when both are required**: **Python & Governance** first, followed by **Frontend & Focused Validation** only when Python succeeds. Frontend-only changes still run the selected frontend/focused lane when Python is legitimately skipped by path-aware routing. If Python fails, the downstream validation lane is skipped immediately rather than continuing expensive pytest after an already decisive failure. The final lightweight aggregate still evaluates all required lane conclusions fail-closed, and a failed Developer Check prevents Full Admission. Redundant parent/child focused-test paths are normalized before pytest execution. This sequencing also avoids simultaneous memory-intensive Pyright and pytest on the shared runner host. It may increase the total wall-clock duration of fully successful two-lane runs, but avoids wasting runner minutes and delaying actionable failures when the earlier lane fails. It does not reduce any selected validation or comprehensive Ready-state gate.

For unusually broad affected-capability Draft candidates, `Frontend & Focused Validation` has a **60-minute job ceiling** (not a target duration). A previous 20-minute ceiling cancelled [#40621151289](https://github.com/OXY7O/KAORI/actions/runs/40621151289) at 96% of selected pytest cases, leaving no complete failure summary. Keep the unchanged path-aware suite, pinned toolchain, isolated PostgreSQL/Redis test project and fail-closed aggregate; a failed or cancelled lane **never** grants Ready or Full Admission. Bounded changes still finish as soon as their selected tests complete. Any future ceiling reduction must follow measured coverage-preserving feedback optimization, not deletion of slow test families.

When selected focused pytest requires backend services, Developer Check uses the existing `.github/ci/compose.yml` PostgreSQL/Redis dependencies in a unique per-run Compose project. Tests execute inside the canonical `ci` service, and teardown removes only that isolated project's ephemeral volumes. This is the established mitigation for missing CI databases; it never shares development or UAT data. Previous shared-host contention investigation #2058 showed simultaneous Pyright and database-backed pytest processes receiving SIGKILL/exit 137 in run #38387513834; concurrency is a suspected factor, not a proven kernel OOM cause without host logs.

A work branch is eligible to become a Ready/frozen candidate only when:

- it is based on or synchronized with the current staging authority;
- Developer Check is green on the exact current Draft head;
- required review discussion is resolved;
- the PR targets `kaori/staging`.

Marking the PR Ready freezes that exact head and reruns Developer Check. Only a successful exact-head Developer Check starts governed Full Admission. A failed/cancelled Developer Check leaves Full Admission skipped. A changed head invalidates the frozen-candidate evidence and must pass Developer Check again before admission.

### Final-candidate and staging admission

When the PR is marked Ready, `.github/workflows/developer-check.yml` first validates the exact frozen head. Its downstream reusable `Full Admission` job calls `.github/workflows/quality.yml` only after Developer Check PASS; feature PRs do not independently trigger Full Admission. The five comprehensive gates execute as one native matrix with `strategy.fail-fast: true` and **temporary `max-parallel: 1` (#2219)** on the shared ~8-GB, 4-vCPU builder. This serializes Functional Tests, Static & Governance, Security, Frontend, and Runtime & DAST **within each Full Admission matrix**, without omitting any gate; the longest Functional Tests gate runs first. A decisive matrix failure cancels all queued siblings, preserving fail-closed CI Admission and unchanged evidence requirements. This is an operator-requested capacity mitigation after repeated process SIGKILL / exit 137 at two-heavy-lane concurrency, **not** a permanent architecture preference: Full Admission will take longer, and one matrix slot does not prevent other repository workflows or processes on the host from competing for RAM. Keep unrelated heavy builder work paused or isolate it operationally. **Restoration criterion:** after RAM is increased or heavy runners are moved to independent hosts, measure representative concurrent peak memory/headroom and complete Full Admission with all five gates, CI Admission, and Ready Admission Guard where applicable before restoring `max-parallel: 2` under a reviewed #2219 follow-up; do not infer readiness from a single green attempt. The native matrix remains `fail-fast: true`; failed/partial reruns are not substitute evidence for the complete required gate set.

### Shared-builder cross-workflow capacity evidence (#2231, #2238)

The temporary `max-parallel: 1` ceiling protects **only the five children of one Full Admission matrix**; it is not a host-wide semaphore. Multiple `kaori-ci` runner registrations on the same physical builder can still pick up an unrelated Draft, Ready, dispatch, or staging job at the same time. Do not claim global isolation or restore two-gate concurrency from a successful serial run alone. A single GitHub `concurrency.group` is not a safe FIFO mutex: newer pending runs can replace earlier pending work.

Before a runner-label, service, or physical-capacity change, the authorized runner operator records the following **read-only** snapshots during an idle period and each intentionally scheduled test window, with UTC timestamps and relevant exact run/job URLs. Do not paste tokens, environment variables, registration credentials, or private runner configuration into issues:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
hostname; nproc; uptime; free -h
grep -E "^(MemTotal|MemAvailable|SwapTotal|SwapFree):" /proc/meminfo
docker info --format "Docker CPUs={{.NCPU}} memory_bytes={{.MemTotal}}"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"
systemctl list-units --all --type=service --no-pager "actions.runner*"
cat /sys/fs/cgroup/memory.events 2>/dev/null || true
```

The host-wide `/sys/fs/cgroup/memory.events` file may not represent individual container or runner-service events; record the actual cgroup path and before/after counters when available. `docker stats --no-stream` and `free -h` are **point-in-time**, not peak RSS; use existing host/container telemetry or the relevant cgroup `memory.peak` for peak evidence where accessible. Record unavailable measurements as gaps rather than inventing headroom.

Use GitHub **Settings → Actions → Runners** to reconcile each registration/label with its physical host and service identity; confirm the selected `runs-on` labels in both `.github/workflows/developer-check.yml` and `.github/workflows/quality.yml`. Count **physical heavy slots**, not runner names. Keep `platform-ci` and `kaori-ci` boundaries distinct. Capture per-job queue wait (`started_at - created_at`), runtime (`completed_at - started_at`), end-to-end duration, memory peak/OOM deltas, and any exit 137 or cancelled result.

Only after operator approval and available headroom, run a controlled two-PR test on distinct candidate heads: first a single Draft/Ready heavy job, then two independently queued heavy flows. Verify no overlap on the physical 8-GB host, **both complete** rather than a pending candidate being replaced, no false PASS or missing mandatory gate, and full cleanup/evidence. Separate same-PR supersession behavior from cross-PR queue safety. Stop and keep the conservative serial policy when OOM events, unknown runner mapping, unbounded queue eviction, or insufficient memory evidence occurs.

**Preferred durable options:** route all memory-heavy jobs through one specifically eligible runner registration on the 8-GB host (with other registrations restricted to truly lightweight workloads), or provide separate physical hosts/adequate RAM before increasing parallelism. This is an option assessment, **not an authorization to relabel, deregister, or restart runners**. Any host workflow must have operator-reviewed maintenance, rollback to the last accepted runner label/service mapping, and a recovery path if the single eligible runner is offline. Update the existing release/runner contracts when routing is actually changed; prove exact-head Developer Check, all five Full Admission gates, CI Admission, staging Fast Smoke, and operational UAT before considering #2219/#2231 complete.

**Approved constrained-host capacity (2026-10-17, #2231): exactly ONE active `kaori-ci` runner on the ~7.8 GiB RAM / no-swap builder.** Two independent heavy workflows previously overlapped and both exited 137; the historical two-active-lane guidance (#665/#673) is superseded for this host. Preserve `quality.yml` five-gate `max-parallel: 1`, Draft/Ready, Security, DAST, CI Admission and immutable evidence. Independent heavy jobs must queue on the single GitHub runner rather than share physical RAM. Do not use a broad GitHub `concurrency.group` because pending runs can be replaced.

The operator verified this exact on-host installation/unit mapping. Recheck each installation's `.service` file, process tree and GitHub Actions runner **names/labels/online status** before any future maintenance:

| Runner installation | Exact systemd unit | Approved state |
| --- | --- | --- |
| `/opt/actions-runner` | `actions.runner.OXY7O.runner-contabo.service` | active/enabled; only `kaori-ci` heavy slot |
| `/opt/actions-runner-02` | `actions.runner.OXY7O.runner-contabo-02.service` | inactive/disabled spare |
| `/opt/actions-runner-03` | `actions.runner.OXY7O.runner-contabo-03.service` | inactive/disabled spare |
| `/opt/actions-workflow` | `actions.runner.OXY7O.platform-contabo.service` | active/enabled; independent `platform-ci` |

**Actual incident and root cause:** former spare `-02` unit had `KillMode=process`. `systemctl disable --now` showed inactive while a Node `RunnerService.js` supervisor and `Runner.Listener` persisted within its cgroup. SIGTERM of the listener alone made the Node supervisor automatically respawn a fresh listener 5 seconds later; that unexpected second slot accepted all five gates from an otherwise successful Full Admission. This is why **service inactive/disabled alone is insufficient** to prove physical isolation.

The approved host-only maintenance sequence is: **first confirm no GitHub job running/queued on the affected runner and no busy Worker**, identify exact `-02` unit/cgroup, disable the two spares, and terminate only the stopped spare's residual cgroup, never all runner processes or Docker:

```bash
SECOND=actions.runner.OXY7O.runner-contabo-02.service
THIRD=actions.runner.OXY7O.runner-contabo-03.service
systemctl status "$SECOND" --no-pager
pgrep -af 'RunnerService.js|Runner.Listener|runsvc.sh' || true
sudo systemctl disable --now "$SECOND" "$THIRD"
# Only after confirming no active work and -02's remaining service cgroup:
sudo systemctl kill --signal=SIGTERM --kill-whom=all "$SECOND"
```

The operator applied drop-ins under `/etc/systemd/system/{exact-spare-unit}.d/10-kaori-cgroup-stop.conf` with `[Service]` / `KillMode=control-group`, then `systemctl daemon-reload`. Both spares must show `KillMode=control-group`, `ActiveState=inactive`, `UnitFileState=disabled`; process inventory after 10+ seconds must show **only** one listener/supervisor from `/opt/actions-runner` and one from `/opt/actions-workflow`. Do **not** change the live main or `platform-ci` units. Keep the drop-ins and existing two spare units for controlled recovery, without deregistering or deleting anything.

**Rollback/recovery:** if the single primary runner fails, drain running work and stop/disable it *before* enabling exactly one verified spare, then switch back only after draining the spare. Never restore two simultaneous physical `kaori-ci` slots without new measured host capacity or separate hosts and operator acceptance. Validate two different mandatory candidate workflows queue and finish without OOM or silently dropped jobs; verify Full Admission, CI Admission, staging Fast Smoke, observed queue time and human infrastructure UAT before closing #2231/#2219. One successful Full Admission by itself does not prove longitudinal no-OOM stability.

After merge to `kaori/staging`, the workflow verifies exact source-tree/authority evidence and transition lineage. Evidence discovery accepts both valid run parents: direct `quality.yml` runs and sequenced `developer-check.yml` caller runs that contain the reusable Full Admission artifact. The evidence payload itself must still identify the governed `quality.yml` authority and pass the existing tree, authority-fingerprint, profile-version, and lineage checks. The normal staging path reuses the admitted evidence and runs fresh Fast Smoke; staging falls back to a fresh Full Admission only when reuse cannot be proven.

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


### Exact-candidate UAT handover

After a governed UAT deploy, retain the handover in the owning GitHub issue, official workflow runs, release metadata, and committed server release state. Do **not** create a second mutable release register. The operator records:

1. **Candidate identity:** intentional RC tag, accepted source SHA, immutable OCI digest, GitHub Release and RC evidence run. Separate source-branch HEAD from the actually deployed candidate.
2. **Machine evidence:** exact-SHA Ready Full Admission (all mandatory lanes and guards), staging push Fast Smoke/CI Admission, RC publication and attestations, and terminal UAT `Release Evidence` and `Deploy Staging` outcomes. Reference the pre-migration backup and migration, internal runtime, queues/Beat and access evidence; report a missing or failed required step as **BLOCKED**, not PASS.
3. **Independent public publication:** record `Reconcile Public Publication` separately, with DNS, HTTP-to-HTTPS, trusted TLS, public readiness and certificate renewal evidence. Internal deployment may succeed before edge reconciliation is finished.
4. **Human acceptance:** link executed scenario IDs, UAT environment, browser/light-dark/responsive/keyboard and protected paths, negative/permission cases, provider read-back, findings and retests to existing Visual QA/UAT issue authority. Mark unexecuted checks **NOT RUN** and unmet prerequisites **BLOCKED**. The human reviewer alone accepts residual risk or the candidate; CI SUCCESS is not Human Acceptance.

**Later staging commits do not rewrite UAT history.** If `kaori/staging` advances beyond the last deployed RC SHA, including a documentation/CI-only merge, retain the RC tag, SHA, digest and actual UAT receipt as the observed deployment identity. Compare the later change to the accepted scope; do not claim the newer staging SHA is deployed, silently reuse an old UAT acceptance for a different source, or automatically dispatch another deployment. Any subsequently chosen deployment or promotion must follow existing exact-SHA admission, new intentional immutable RC, governed UAT evidence and human acceptance.

For the **2026-10-20** [#1710 technical receipt](https://github.com/OXY7O/KAORI/issues/1710), the UAT release was [v0.3.0-rc.11](https://github.com/OXY7O/KAORI/releases/tag/v0.3.0-rc.11) at `8b5b365f6d41724d146743fa329800d955ee9740`, proven by [Staging Deploy #39351114282](https://github.com/OXY7O/KAORI/actions/runs/39351114282). The later CI-governance-only staging merge [PR #2577](https://github.com/OXY7O/KAORI/pull/2577), at `9f98ed45af621d00e432ea08449d514c1068ac29`, is **not** that UAT deployment identity. The disposable-UAT restore-rehearsal exception [#2206](https://github.com/OXY7O/KAORI/issues/2206) remains **not a restore PASS**; the database-role cutover [#1439](https://github.com/OXY7O/KAORI/issues/1439) remains separate.

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

Roll-forward requires a new governed issue-branch change, fresh Draft Developer Check, a new frozen Ready candidate, exact-head Developer Check PASS, Full Admission for that candidate, staging evidence reuse/Fast Smoke, a new immutable RC, deployment verification, and the same human acceptance boundary.

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
