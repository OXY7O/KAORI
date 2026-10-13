# KAORI Retrospective UAT — First-Wave Executable Scenario Specifications

**Scope:** #1738 retrospective acceptance catalog, under #1724. This companion document expands selected IDs from [KAORI_UAT_SCENARIO_CATALOG.md](KAORI_UAT_SCENARIO_CATALOG.md). The normative record fields/decisions belong to `docs/TESTING.md` in #1725; these are *proposed test specifications*, not test run reports.

**Discovery baseline:** `kaori/review/staging-uat@0415d1832adcdb7bd30bd3f2d32e4940c90335af` (source review); revalidate against eventual accepted staging SHA and canonical domain authority before executing. **Every case below: implementation mapping UNVERIFIED, execution NOT RUN, human acceptance PENDING.** No browser, provider, server or CI runs are evidenced by this document.

## Execution preparation

1. Read the owning domain documentation and controlling issue; verify that the scenario's exact feature/action exists and is admitted on the **selected** candidate. A planned/disabled operation is tested as unavailable, not as successful.
2. Map each scenario to actual pytest/Playwright node IDs by reading assertions; existing paths listed below are **candidates only**. Use the existing runner and shared fixtures; do not add a Cucumber runner or parallel QA framework.
3. Record source SHA and tree, environment, role, actual setup, test runner identity, exact provider/database fixture IDs and whether proof is mocked or real. For deployed server UAT, include exact OCI digest.
4. For UI cases, use real browser click/fill/select/submit and check UI **plus** persisted/domain outcome where relevant. Include normal and error state, light/dark and canonical viewport coverage scoped to the case. Do not silently rebaseline visuals.
5. For all negative mutations, compare before/after KAORI committed state **and** external provider state; verify no false success. Test destructive/provider writes only on explicit sandbox fixture with governed cleanup.
6. Store sanitized JUnit, screenshot, trace, audit/correlation and provider read-back in existing evidence paths. A runner SKIP/blocked/missing evidence cannot become PASS. Human reviewer decision is separate.

## Detailed scenario procedures

### UAT-AUT-002 — Invalid login never admits a session

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** A test account exists; a known invalid password can be supplied. Use only disposable credentials.

**Steps:**
1. Open the canonical sign-in page with Playwright.
2. Fill username and invalid password; click submit.
3. Attempt to navigate directly to a protected capability URL and inspect server session state.

**Expected results:**
- No authenticated session or protected content is granted.
- The form displays an actionable, non-enumerating authentication failure.
- No token, password or private identity data appears in screenshot/trace/audit.

**Required evidence:** Browser trace, sanitized response, session/access assertion and server-side auth result.

**Candidate test ownership (not confirmed executable mapping):** `tests/access/authentication/`, `tests/security/access/`, `tests/ui/`

**Isolation / cleanup:** Never publish credential input or auth cookie in CI traces.

### UAT-IAM-002 — Restricted user cannot mutate Users or Roles through direct requests

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Two local test principals with known disjoint role permissions and disposable User/Role fixtures.

**Steps:**
1. Sign in as a restricted user; confirm role mutation action is not falsely advertised.
2. Invoke a direct protected mutation URL/API as that user, including valid CSRF material when relevant.
3. Read User/Role records and Activity to inspect post-request state.

**Expected results:**
- Server rejects unauthorized access regardless of UI visibility.
- No role membership, privilege or administrative object changes.
- Error response/UI is safe and does not leak sensitive role details.

**Required evidence:** Playwright response and screenshot, denied permission assertion, before/after persisted state.

**Candidate test ownership (not confirmed executable mapping):** `tests/contracts/access/`, `tests/security/access/`, `tests/access/users/`

**Isolation / cleanup:** Do not test escalation on a production administrative identity.

### UAT-TEN-001 — Native Namespace adoption preserves provider authority

**Kind:** Positive / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Approved disposable Native Namespace not owned by KAORI, baseline UID/resourceVersion, test operator with adoption permission; no Capsule ownership.

**Steps:**
1. Capture Kubernetes Namespace UID/resourceVersion, labels/owner references and applicable quota before test.
2. Navigate to Tenant Discovery/Adoption and select the exact Namespace.
3. Review Preflight and explicitly confirm the allowed adoption.
4. Inspect KAORI Tenant/Namespace committed record, generation and Activity; read back provider Namespace by exact UID.

**Expected results:**
- Exactly one adopted generation under correct cluster/provider/tenant scope.
- Committed evidence identifies the verified provider object; no duplicate governance owner.
- Only explicitly admitted provider writes occur; audit/mutation provenance is truthful.

**Required evidence:** Pre/post provider identity and object diff, UI screenshot/trace, committed Tenant/Namespace fields and Audit correlation.

**Candidate test ownership (not confirmed executable mapping):** `tests/kubernetes/tenant/`, `tests/contracts/kubernetes/`, `tests/ui/`

**Isolation / cleanup:** Disposable Native Namespace only, read-back required and cleanup/recovery governed.

### UAT-TEN-002 — Stale Native Namespace preflight must fail closed

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Approved disposable Native Namespace; controlled test fixture may change its resourceVersion between valid Preflight and submit.

**Steps:**
1. Record baseline provider UID, resourceVersion and KAORI adopted records.
2. Complete Discovery and Preflight through browser.
3. Change Namespace resourceVersion through an approved isolated fixture.
4. Submit the original stale form and inspect UI response, KAORI database and provider read-back.

**Expected results:**
- No successful adoption; actionable error rather than success toast.
- No new adopted Tenant/Namespace generation and no unauthorized provider mutation.
- Audit does not falsely claim successful adoption; failed attempt can be correlated.

**Required evidence:** Version before/after, browser trace, response, DB diff, provider diff and Audit.

**Candidate test ownership (not confirmed executable mapping):** `tests/kubernetes/tenant/`, `tests/contracts/kubernetes/`, `tests/ui/`

**Isolation / cleanup:** Use only approved test Namespace; do not create a conflict on real operational workloads.

### UAT-TEN-004 — Capacity budget rejection prevents allocation mutation

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** A disposable Tenant allocation/provisioning fixture with committed capacity evidence and a proposed change exceeding available governed headroom.

**Steps:**
1. Open Namespace Provisioning/Allocation Change as allowed operator.
2. Enter an allocation exceeding the accepted cluster budget.
3. Inspect preview/shortfall/readiness, then attempt submit via UI or direct request.
4. Compare committed allocation version and provider ResourceQuota/LimitRange before and after.

**Expected results:**
- Preview shows truthful shortfall and blocks mutation.
- Server independently rejects an invalid/out-of-budget submit.
- Pinned allocation and provider quota/limits remain unchanged with no success audit.

**Required evidence:** Form/preview screenshot, validation response, capacity source fingerprint, committed version and provider read-back.

**Candidate test ownership (not confirmed executable mapping):** `tests/kubernetes/tenant/test_capacity_governance.py`, `tests/kubernetes/tenant/test_allocation_cutover.py`, `tests/ui/`

**Isolation / cleanup:** Never use a production allocation for boundary-failure testing.

### UAT-KOP-004 — Secret reveal rejects user without approved policy

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Synthetic Secret in disposable namespace; test user lacks reveal policy/approval. Do not use real secret values.

**Steps:**
1. Visit permitted Kubernetes Administration/Secret Reveal surfaces as restricted user.
2. Attempt to open a protected reveal flow; also invoke direct reveal request where safe.
3. Inspect response, Activity, trace/log redaction and Secret state.

**Expected results:**
- Reveal is denied before any one-time disclosure occurs.
- Secret value never appears in browser DOM, response, screenshot, trace or logs.
- No false approved/revealed audit is recorded.

**Required evidence:** Denied HTTP/permission assertion, sanitized browser trace, audit state and negative secret-leak assertions.

**Candidate test ownership (not confirmed executable mapping):** `tests/security/kubernetes/`, `tests/platform_operations/test_secret_reveal_htmx_save.py`, `tests/kubernetes/operations/`

**Isolation / cleanup:** Only non-sensitive known fixture Secret; redact every captured artifact.

### UAT-ING-002 — Invalid provider credentials/TLS do not produce Ready state

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Isolated Metrics Source, Alertmanager or Object Storage provider test instance with deliberately invalid validation inputs.

**Steps:**
1. Open the existing capability-first Integrations instance/configuration form.
2. Fill a non-secret invalid endpoint/certificate or disposable invalid credentials.
3. Trigger the owning provider validation and inspect operational UI feedback.
4. Inspect committed readiness/evidence and bound consuming views.

**Expected results:**
- Provider validation is rejected or degraded, never marked Ready.
- No fallback to another instance or cross-scope/source substitution.
- No sensitive validation payload in UI/audit/traces.

**Required evidence:** UI modal/validation trace, provider result, committed instance state, consumer posture and safe audit.

**Candidate test ownership (not confirmed executable mapping):** `tests/integrations/`, `tests/contracts/integrations/`, `tests/ui/`

**Isolation / cleanup:** Use deliberate invalid sandbox configuration; preserve existing live integration instance configuration.

### UAT-REG-003 — Stale artifact-to-runtime identity cannot claim verified binding

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Two distinct registry/runtime identities or stale runtime snapshot fixture; no provider writes required.

**Steps:**
1. Record artifact registry identity and currently committed runtime binding evidence.
2. Make target cluster/runtime evidence stale, missing or identity-mismatched in fixture.
3. Open Runtime Usage/Topology details and inspect binding status.
4. Check underlying normalized correlation status against source fingerprint.

**Expected results:**
- UI labels missing/unverified/stale binding truthfully, not verified/Ready.
- No false artifact-to-runtime link or cross-cluster association is committed.
- UI remains navigable and usable in error/unknown state at supported viewports.

**Required evidence:** Normalized binding assertion, source fingerprint, UI detail screenshot, trace and empty/degraded state.

**Candidate test ownership (not confirmed executable mapping):** `tests/contracts/artifact_registry/`, `tests/unit/artifact_registry/`, `tests/ui/`

**Isolation / cleanup:** Read-only fixture; no registry image or cluster resource mutation.

### UAT-RPT-001 — Report generation respects exact selected source and format

**Kind:** Positive / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Reports worker/queue, one registered supported infrastructure source, disposable output bucket/path, permitted user.

**Steps:**
1. Open Reports → Generate as permitted test principal.
2. Select one exact source scope and supported report family and output format.
3. Submit request; capture queued job, completion and generated artifact metadata.
4. Inspect actual PDF/XLSX/CSV structure and source identity where suitable.

**Expected results:**
- Job is admitted once under canonical Reports execution; no wrong-source fallback.
- Generated artifact type and content match selected scope/format.
- Generated registry and storage metadata show correct state, size and safe access.

**Required evidence:** Browser trace, JobExecution/correlation, artifact metadata, test renderer assertions and cleanup.

**Candidate test ownership (not confirmed executable mapping):** `tests/reports/test_generate_execution_characterization.py`, `tests/reports/test_report_catalog.py`, `tests/contracts/reports/`

**Isolation / cleanup:** Isolated Reports worker/storage; remove generated test artifacts safely.

### UAT-RPT-003 — Reports worker/storage failure does not show generated success

**Kind:** Negative / UI + Non-UI · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Disposable Reports queue/storage test environment with controlled worker unavailable or storage write failure.

**Steps:**
1. Select valid bounded report request from the UI.
2. Simulate worker unavailable, renderer failure or storage rejection through isolated test fixture.
3. Open Generated Reports and Jobs to inspect requested and terminal states.
4. Compare artifact existence, JobExecution and Activity outcome.

**Expected results:**
- No generated artifact falsely listed as ready/downloadable.
- Error/blocked feedback truthfully identifies the failure while protecting internals.
- Job/audit state and storage record are consistent and retry is explicit if permitted.

**Required evidence:** UI loading/error screenshots, worker logs (sanitized), JobExecution, artifact store absence and metadata.

**Candidate test ownership (not confirmed executable mapping):** `tests/reports/`, `tests/contracts/reports/`, `tests/platform_operations/jobs/`

**Isolation / cleanup:** Do not stop live Reports workers or delete real artifact storage.

### UAT-LIF-002 — Unverified archive blocks retention cleanup

**Kind:** Negative / Non-UI + UI state · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Dedicated disposable lifecycle records and archive sink configured to fail verification; cleanup path isolated.

**Steps:**
1. Prepare a policy and candidate lifecycle records in sandbox.
2. Cause archive destination/read-back verification to fail deterministically.
3. Attempt the governed lifecycle execution; inspect job, archive and UI outcome.
4. Verify original records remain present and no cleanup is reported successful.

**Expected results:**
- No destructive purge of unverified data.
- Job/Archive/Audit evidence shows failure or blocked action, not success.
- Operator is given safe recovery/next action without silently retrying destruction.

**Required evidence:** Record IDs pre/post, archive read-back, JobExecution, failed verification and UI error state.

**Candidate test ownership (not confirmed executable mapping):** `tests/contracts/platform_operations/`, `tests/platform_operations/`, `tests/integration/`

**Isolation / cleanup:** Never inject failure into live retention/purge, production backups or non-disposable records.

### UAT-UIX-002 — Modal remains accessible at 360×800 after validation

**Kind:** Negative / UI Visual QA · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Authenticated browser fixture with a real form/modal in an available KAORI capability; deterministic content and viewport 360×800.

**Steps:**
1. Open actual modal/drawer using Playwright click, not by injecting hidden CSS classes.
2. Fill invalid value; click submit to trigger validation and any HTMX replacement.
3. Assert dialog bounds, visible primary/secondary actions, focus/error association and no document horizontal overflow.
4. Capture screenshots before open, after open and after validation in light and dark where applicable.

**Expected results:**
- All accessible actions remain reachable; modal body scrolls when needed.
- No clipped Save/Cancel buttons, hidden validation text or focus lost behind overlay.
- No unauthorized form submission or successful toast when validation failed.

**Required evidence:** Playwright trace/screenshots, bounding boxes, keyboard navigation assertion and error state.

**Candidate test ownership (not confirmed executable mapping):** `tests/ui/test_representative_interactions.py`, `tests/ui/visual_audit.py`, `tests/ui/test_accessibility_disclosures.py`

**Isolation / cleanup:** Deterministic test fixtures; do not auto-update baselines based on failed geometry.

### UAT-UIX-004 — Geometry regressions fail instead of approving poor baseline

**Kind:** Negative / UI Design Contract · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Reviewed KAORI Violet/shared Hero/table baseline and deterministic example page including a controlled changed layout fixture.

**Steps:**
1. Render a real audited page with source-equivalent frontend CSS at 1440×900 and 390×844.
2. Apply a narrowly controlled fixture that causes Hero wrapping, clipped primary action, or modal overflow.
3. Run existing executable visual geometry assertions, then screenshot comparison.
4. Inspect evidence and restore fixture/baseline unchanged.

**Expected results:**
- Actual rendered geometry violation fails even if source-length/style checks pass.
- Screenshot/diff and precise invariant identify affected surface/viewport/theme.
- Reviewed baselines are preserved; no silent acceptance or arbitrary AI visual score.

**Required evidence:** Playwright assertion, original/actual screenshot, trace and baseline-diff finding.

**Candidate test ownership (not confirmed executable mapping):** `tests/ui/visual_audit.py`, `tests/ui/test_visual_audit_contract.py`, `tests/ui/test_representative_interactions.py`

**Isolation / cleanup:** No mutation to approved screenshot baselines in a normal test run.

### UAT-REL-002 — Wrong OCI digest never deploys as accepted candidate

**Kind:** Negative / Release UAT · **Risk:** High · **Execution:** NOT RUN · **Automation mapping:** UNVERIFIED · **Human acceptance:** PENDING

**Preconditions:** Existing accepted staging SHA/image digest identity, governed release evidence and safe mock/isolated deployment preflight. No production deploy.

**Steps:**
1. Construct a candidate request with mismatched SHA/digest or stale accepted candidate identity.
2. Run canonical delivery preflight/contract verifier only against isolated fixtures.
3. Compare permitted release/deploy intent and previous accepted release identity.
4. Inspect actionable rejection/error evidence.

**Expected results:**
- Request rejected before changing running image or marking UAT accepted.
- Current release digest, state and recovery authority unchanged.
- No invented PASS, promotion or release tag is recorded.

**Required evidence:** Preflight output, immutable candidate metadata assertions, rejected request and no-mutation proof.

**Candidate test ownership (not confirmed executable mapping):** `tests/contracts/release/`, `tests/integration/release/`

**Isolation / cleanup:** Never manually dispatch deploy/release workflow for a negative test on real staging host.

Source assertion audit: [KAORI_UAT_TEST_MAPPING_AUDIT.md](KAORI_UAT_TEST_MAPPING_AUDIT.md). Its PARTIAL/SOURCE-CONTRACT classifications reflect inspected tests only; the execution table remains NOT RUN until candidate-bound results exist.

## First-wave mapping checklist (NOT RUN)

Do not confuse a file path with implemented acceptance assertions. For each case, an owning engineer must identify one or more verified test node IDs, record what **each** assertion proves (UI, domain/DB, provider/audit, negative failure), and list remaining gaps. An existing source contract alone does not prove a user journey. The table below is a mapping worklist rather than execution results.

| Scenario ID | Verified node IDs | UI oracle | Domain/DB oracle | Provider/audit oracle | Actual run evidence |
| --- | --- | --- | --- | --- | --- |
| `UAT-AUT-002` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-IAM-002` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-TEN-001` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-TEN-002` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-TEN-004` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-KOP-004` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-ING-002` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-REG-003` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-RPT-001` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-RPT-003` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-LIF-002` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-UIX-002` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-UIX-004` | Pending | Pending | Pending | Pending | NOT RUN |
| `UAT-REL-002` | Pending | Pending | Pending | Pending | NOT RUN |

**After real execution:** link sanitized artifacts and results in the governing Issue/PR comment, link any remediation issue, and retain previous attempt identity. #1726/#1727 implement missing coverage; #1728 will enforce required execution/evidence only after approval. #1730 owns formal human acceptance against the exact admitted candidate.
