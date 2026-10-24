# KAORI Retrospective UAT — Existing Test Assertion Audit

**Authority:** #1738 / #1724. This is a **read-only source assertion mapping** for 14 first-wave cases in [KAORI_UAT_FIRST_WAVE_CASES.md](KAORI_UAT_FIRST_WAVE_CASES.md). Normative scenario contract: #1725 / `docs/TESTING.md`. **This file is not a test execution report and cannot support UAT PASS.**

**Source inspected:** `kaori/review/staging-uat@0415d1832adcdb7bd30bd3f2d32e4940c90335af`; initial work branch from `kaori/staging@79bbb7466c60b9781358c3e26faf476ab0c54bf1`. Test functions were inspected by reading their assertions, not merely by discovering file names. Only specified excerpts/tests were reviewed; additional ownership can exist elsewhere and must be evaluated before claiming absence of all coverage.

## Evidence vocabulary

- **PARTIAL — behavioral:** an existing test actually asserts a relevant input/output, validation, state, or browser behavior; it does **not** prove the full acceptance sequence or provider/UAT outcome.
- **SOURCE-CONTRACT ONLY:** relevant test verifies source structure, static string/invariants, or another adjacent component; the complete business-negative or browser scenario was **not demonstrated** by inspected assertions.
- **Missing from initial staging:** when marked review-only, the named test file existed on inspected reviewed candidate but returned 404 when fetched from the initial staging-based work branch. Do not assume it is already available on staging until integrated.
- **PASS / FAIL / SKIP:** no scenario execution verdict is recorded in this audit. All 14 are **NOT RUN** on any selected candidate as scenario IDs; **human acceptance PENDING**.

## Source-level mapping summary

| Scenario | Mapping from inspected assertions | Available at work-branch baseline? | Evidence gap |
| --- | --- | --- | --- |
| `UAT-AUT-002` | PARTIAL — non-UI behavior + adjacent browser validation | Yes, referenced test files readable | No evidenced Playwright wrong-password submit plus server session/role rejection and protected-route attempt on the same browser flow. |
| `UAT-IAM-002` | SOURCE-CONTRACT ONLY (for direct user/role mutation denial) | Yes, referenced test files readable | Run actual restricted user session and direct role/user mutation, assert HTTP deny and persisted/effective permissions unchanged; add browser visibility/state test. |
| `UAT-TEN-001` | PARTIAL — domain identity validation | Review candidate only for named tests | No verified actual browser Discovery→Preflight→Adopt path, exact committed Tenant generation and post-mutation disposable Kubernetes provider read-back. Named test file absent in initial staging. |
| `UAT-TEN-002` | PARTIAL — negative domain validation | Review candidate only for named tests | Missing verified real browser stale submit and full before/after provider/DB/audit assertions in one scenario; named test file absent in initial staging. |
| `UAT-TEN-004` | PARTIAL — risk-relevant capacity service tests | Yes, referenced test files readable | Missing verified Playwright allocation preview/submit with same acceptance fixture and controlled ResourceQuota/LimitRange read-back proving no mutation. |
| `UAT-KOP-004` | SOURCE-CONTRACT ONLY (for forbidden Secret Reveal) | Yes, referenced test files readable | Execute a forbidden reveal request under restricted identity with synthetic secret, assert server deny, no secret disclosure in DOM/response/log/trace/audit. |
| `UAT-ING-002` | PARTIAL — provider service readiness + TLS boundary | Yes, referenced test files readable | Not yet a verified Playwright instance edit→invalid credentials/TLS→validation error flow with persisted readiness/consumer read-back for each mandatory provider type. |
| `UAT-REG-003` | PARTIAL — runtime correlation identity/readiness | Review candidate only for named tests | No verified browser Runtime Usage/Topology stale-details interaction or combined normalized materialization/committed read-back; runtime-readiness test file absent in initial staging. |
| `UAT-RPT-001` | PARTIAL — report request persistence, not artifact completion | Yes, referenced test files readable | No verified Playwright Generate wizard interaction followed by actual worker completion, correctly scoped PDF/XLSX/CSV generation, artifact read-back and cleanup. |
| `UAT-RPT-003` | SOURCE-CONTRACT / COMPONENT ONLY for complete worker/storage failure scenario | Yes, referenced test files readable | Introduce isolated worker/storage failure injection and assert JobExecution, storage absence and Generated UI error/no false Ready after submit. |
| `UAT-LIF-002` | SOURCE-CONTRACT ONLY (for archive-before-cleanup safety) | Review candidate only for named tests | Run isolated archive verification failure at service boundary; prove original records retained and JobExecution/audit/UX state without destructive cleanup. |
| `UAT-UIX-002` | PARTIAL — shared overlay and separate form validation | Yes, referenced test files readable | No evidenced same-flow real mutation modal on small mobile viewport with invalid field, validation response, overlay bounds, focus/scroll and screenshot AFTER error. |
| `UAT-UIX-004` | PARTIAL — deterministic geometry + synthetic signature | Yes, referenced test files readable | No verified controlled geometry failure fixture on broader active authenticated route / modal with full measured clipping assertion; screenshot signature is not aesthetic approval. Existing deterministic surfaces are only Welcome, Settings General, Notification Center. |
| `UAT-REL-002` | SOURCE-CONTRACT ONLY (for mismatched digest rejection execution) | Yes, referenced test files readable | No verified isolated negative preflight invocation with a mismatched digest plus no-deploy/no-release-side-effect assertion. Never run intentionally bad release against actual UAT host. |

## Detailed per-scenario test nodes and precise limitations

### UAT-AUT-002 — PARTIAL — non-UI behavior + adjacent browser validation

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/access/authentication/test_login_characterization.py::test_invalid_credentials_return_generic_failure_without_account_disclosure`
  - `tests/ui/test_accessibility_disclosures.py::test_login_validation_errors_are_programmatically_associated`
- **What those assertions establish:** Flask client invalid-credential request records an invalid-credential result and non-disclosing feedback; Playwright fills empty fields and verifies accessible validation errors.
- **Still required:** No evidenced Playwright wrong-password submit plus server session/role rejection and protected-route attempt on the same browser flow.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-IAM-002 — SOURCE-CONTRACT ONLY (for direct user/role mutation denial)

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/security/access/authentication/test_authentication_security.py::test_login_and_logout_keep_csrf_and_post_only_boundaries`
  - `tests/contracts/access/test_role_create_clone_rollback_contract.py::test_role_create_clone_database_failure_routes_are_bounded`
- **What those assertions establish:** Static/contract guards for authentication route, role transaction rollback and form handlers. Does not execute the restricted-user-to-mutating-endpoint scenario.
- **Still required:** Run actual restricted user session and direct role/user mutation, assert HTTP deny and persisted/effective permissions unchanged; add browser visibility/state test.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-TEN-001 — PARTIAL — domain identity validation

- **Inspected source availability:** review-only named adoption-identity tests.
- **Concrete inspected test node IDs:**
  - `tests/kubernetes/tenant/test_new_tenant_adoption_identity.py::test_native_and_capsule_adoption_pins_exact_uid_and_version_from_preflight`
  - `tests/kubernetes/tenant/test_new_tenant_adoption_identity.py::test_new_tenant_adoption_rolls_back_pending_governance_after_provider_error`
- **What those assertions establish:** Positive provider UID/version equality and provider-failure rollback assertions are present in reviewed candidate.
- **Still required:** No verified actual browser Discovery→Preflight→Adopt path, exact committed Tenant generation and post-mutation disposable Kubernetes provider read-back. Named test file absent in initial staging.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-TEN-002 — PARTIAL — negative domain validation

- **Inspected source availability:** review-only named adoption-identity tests.
- **Concrete inspected test node IDs:**
  - `tests/kubernetes/tenant/test_new_tenant_adoption_identity.py::test_new_tenant_adoption_rejects_missing_or_changed_provider_identity`
  - `tests/kubernetes/tenant/test_new_tenant_adoption_identity.py::test_new_tenant_adoption_rolls_back_when_database_commit_fails`
- **What those assertions establish:** Pytest expects ValueError on changed UID/resourceVersion and asserts a DB rollback path for commit failure.
- **Still required:** Missing verified real browser stale submit and full before/after provider/DB/audit assertions in one scenario; named test file absent in initial staging.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-TEN-004 — PARTIAL — risk-relevant capacity service tests

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/kubernetes/tenant/test_capacity_governance.py::test_preflight_blocks_projected_shortfall`
  - `tests/kubernetes/tenant/test_capacity_governance.py::test_stale_committed_capacity_snapshot_fails_closed`
  - `tests/kubernetes/tenant/test_capacity_governance.py::test_positive_change_is_blocked_while_cluster_is_already_overcommitted`
- **What those assertions establish:** Executable service tests reject over-budget preflight, stale capacity, and increasing overcommit.
- **Still required:** Missing verified Playwright allocation preview/submit with same acceptance fixture and controlled ResourceQuota/LimitRange read-back proving no mutation.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-KOP-004 — SOURCE-CONTRACT ONLY (for forbidden Secret Reveal)

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/security/kubernetes/operations/test_kubernetes_operations_security.py::test_secret_security_boundaries_keep_sensitive_values_out_of_persistence_and_reveal`
  - `tests/platform_operations/test_secret_reveal_htmx_save.py::test_secret_reveal_htmx_save_returns_workspace_without_redirect`
- **What those assertions establish:** Source contract asserts scrub/lock boundaries; Flask HTMX policy-save route output is tested. Neither proves unauthorized Secret value reveal blocked in a real negative flow.
- **Still required:** Execute a forbidden reveal request under restricted identity with synthetic secret, assert server deny, no secret disclosure in DOM/response/log/trace/audit.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-ING-002 — PARTIAL — provider service readiness + TLS boundary

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/integrations/test_harbor_readiness.py::test_full_validation_blocks_when_required_repository_capability_is_missing`
  - `tests/integrations/test_harbor_readiness.py::test_failure_recorder_persists_normalized_detail_without_raw_secret`
  - `tests/integrations/test_kubernetes_scoped_tls_transport.py::test_legacy_tls_refuses_unscopable_transport_without_global_fallback`
- **What those assertions establish:** Provider validation can remain blocked when a required capability is missing; failure detail is sanitized; transport rejects unsafe TLS fallback.
- **Still required:** Not yet a verified Playwright instance edit→invalid credentials/TLS→validation error flow with persisted readiness/consumer read-back for each mandatory provider type.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-REG-003 — PARTIAL — runtime correlation identity/readiness

- **Inspected source availability:** review-only named runtime-readiness unit tests.
- **Concrete inspected test node IDs:**
  - `tests/unit/artifact_registry/test_registry_runtime_evidence_readiness.py::test_correlation_readiness_detects_changed_committed_generations`
  - `tests/unit/artifact_registry/test_registry_runtime_identity.py::test_runtime_correlation_does_not_infer_missing_or_foreign_registry_authority`
- **What those assertions establish:** Unit tests assert stale-generation status and forbid inference from missing/foreign registry authority.
- **Still required:** No verified browser Runtime Usage/Topology stale-details interaction or combined normalized materialization/committed read-back; runtime-readiness test file absent in initial staging.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-RPT-001 — PARTIAL — report request persistence, not artifact completion

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/reports/test_generate_execution_characterization.py::test_create_report_request_commits_record_for_fresh_session_readback`
  - `tests/reports/test_generate_execution_characterization.py::test_generate_route_denies_user_without_reports_generate_permission`
- **What those assertions establish:** Test uses isolated SQLite and ensures a requested report record persists; Flask route denies missing generate permission.
- **Still required:** No verified Playwright Generate wizard interaction followed by actual worker completion, correctly scoped PDF/XLSX/CSV generation, artifact read-back and cleanup.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-RPT-003 — SOURCE-CONTRACT / COMPONENT ONLY for complete worker/storage failure scenario

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/contracts/reports/test_generated_reports_final_audit_20260815_contract.py::test_archived_missing_artifact_is_not_offered_as_restorable_evidence`
  - `tests/reports/test_generate_execution_characterization.py::test_create_report_request_commits_record_for_fresh_session_readback`
- **What those assertions establish:** Source assertions protect archived missing-artifact display; request persistence is covered separately. Reviewed evidence did not establish injected worker/storage failure with complete job+artifact UI response.
- **Still required:** Introduce isolated worker/storage failure injection and assert JobExecution, storage absence and Generated UI error/no false Ready after submit.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-LIF-002 — SOURCE-CONTRACT ONLY (for archive-before-cleanup safety)

- **Inspected source availability:** review-only named archive reverify contracts.
- **Concrete inspected test node IDs:**
  - `tests/contracts/platform_operations/test_data_lifecycle_archive_reverify_contract.py::test_archive_reverification_rejects_purged_and_nonverifiable_states`
  - `tests/contracts/platform_operations/test_data_lifecycle_archive_reverify_contract.py::test_failed_verification_revokes_readiness_and_downloadability`
- **What those assertions establish:** Static source assertions check nonverifiable/failed archival handling; no actual retention cleanup failure execution observed. Named contract file absent in initial staging.
- **Still required:** Run isolated archive verification failure at service boundary; prove original records retained and JobExecution/audit/UX state without destructive cleanup.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-UIX-002 — PARTIAL — shared overlay and separate form validation

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/ui/test_representative_interactions.py::test_representative_htmx_modal_or_drawer_interaction`
  - `tests/ui/test_accessibility_disclosures.py::test_login_validation_errors_are_programmatically_associated`
- **What those assertions establish:** Playwright really clicks Notification Deck and validates visibility; separately fills login fields and validates aria-invalid/aria-describedby.
- **Still required:** No evidenced same-flow real mutation modal on small mobile viewport with invalid field, validation response, overlay bounds, focus/scroll and screenshot AFTER error.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-UIX-004 — PARTIAL — deterministic geometry + synthetic signature

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/ui/test_representative_interactions.py::test_deterministic_visual_surface_catalog_light_and_dark`
  - `tests/ui/test_visual_audit_contract.py::test_visual_thumbnail_normalizes_raster_noise_without_masking_geometry_regression`
- **What those assertions establish:** Playwright exercises current deterministic surface set for geometry/light/dark/six viewports; Pillow synthetic image test catches changed thumbnail signatures.
- **Still required:** No verified controlled geometry failure fixture on broader active authenticated route / modal with full measured clipping assertion; screenshot signature is not aesthetic approval. Existing deterministic surfaces are only Welcome, Settings General, Notification Center.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

### UAT-REL-002 — SOURCE-CONTRACT ONLY (for mismatched digest rejection execution)

- **Inspected source availability:** staging & review.
- **Concrete inspected test node IDs:**
  - `tests/contracts/release/test_stable_release_reuses_accepted_rc_digest_contract.py::test_stable_release_verifies_registry_rc_and_promotes_same_digest`
  - `tests/contracts/release/test_oci_release_artifact_contract.py::test_stable_promotion_remains_digest_preserving`
- **What those assertions establish:** String/source contract assertions require immutable digest identity, verification and digest-preserving release flow.
- **Still required:** No verified isolated negative preflight invocation with a mismatched digest plus no-deploy/no-release-side-effect assertion. Never run intentionally bad release against actual UAT host.
- **Execution:** NOT RUN; **UAT acceptance:** PENDING. All listed tests are source references, not verified runtime PASS evidence.

## Supplemental source assertion audit — 2026-10-16 (nine additional scenarios)

This checkpoint extends the **original 14 first-wave assertion reviews** with **nine additional owner-review IDs**, without changing the normative scenario specifications or invoking pytest/Playwright. Source test functions below were fetched from the repository and their actual assertions inspected, rather than inferred from their names. Work-branch references are from `kaori/task-1738-retrospective-qa-scenarios` unless explicitly marked **review-only** (`kaori/review/staging-uat`): a review-only test is **not available on this staging-based branch** and must not be counted as branch-executable.

A mapped **partial sub-invariant** is not a complete scenario-to-test mapping. A **source-contract-only** check cannot establish server-side rejection/worker behavior or actual browser interaction. **Adjacent-only** means the inspected test observes a neighboring surface, not the requested scenario itself. No result below is an executed PASS. Scenario status **NOT RUN**, human acceptance **PENDING** throughout.

| Scenario | Inspected exact test node and branch | What the assertion actually covers | Remaining acceptance gap |
| --- | --- | --- | --- |
| `UAT-AUT-001` | `tests/access/authentication/test_login_characterization.py::test_login_page_renders_compact_authentication_surface` — work branch | **ADJACENT ONLY**: GET login page returns HTTP 200 and expected login surface elements | No valid credential POST, authenticated server session, authorized protected navigation or positive authentication Activity evidence |
| `UAT-AUT-004` | `tests/security/access/authentication/test_authentication_security.py::test_login_and_logout_keep_csrf_and_post_only_boundaries` — work branch | **SOURCE-CONTRACT ONLY**: login/logout route declarations and `form.hidden_tag()` are present | No missing/malformed CSRF direct POST rejection, persisted-state no-write assertion or actual user error flow |
| `UAT-AUT-005` | `tests/security/access/authentication/test_authentication_security.py::test_login_and_logout_keep_csrf_and_post_only_boundaries` — work branch | **SOURCE-CONTRACT ONLY**: logout is declared POST-only and guarded by login | No browser logout→Back/bookmark attempt or fresh protected-route session invalidation assertion |
| `UAT-TEN-003` | `tests/kubernetes/tenant/test_capacity_governance.py::test_create_preflight_allows_allocation_inside_budget` — work branch | **PARTIAL SUB-INVARIANT**: capacity preflight allows a budget-compatible proposed allocation | No Resource Profile version pinning, authorized Tenant/Namespace create UI, DB commit, ResourceQuota/LimitRange or disposable provider read-back |
| `UAT-TEN-006` | `tests/kubernetes/tenant/test_new_tenant_adoption_identity.py::test_new_tenant_adoption_rolls_back_when_database_commit_fails` and `::test_new_tenant_adoption_rolls_back_pending_governance_after_provider_error` — **review-only** | **PARTIAL**: injected database commit conflict triggers rollback; separate provider read-back error triggers rollback; the two tests do not establish a completed provider patch | Missing deliberate provider-success+commit-failure fixture with residue/read-back, recoverability, JobExecution/Activity and truthful UI status; tests absent from work branch |
| `UAT-TEN-008` | `tests/kubernetes/tenant/test_new_tenant_adoption_identity.py::test_native_discovery_blocks_orphaned_or_foreign_ownership_before_adoption` and `::test_capsule_new_tenant_adoption_rejects_namespace_owned_by_another_tenant` — **review-only** | **PARTIAL**: native discovery rejects orphaned/foreign ownership labels; Capsule adoption rejects Namespace already assigned to another governed Tenant | No released/re-created UID or generation replay across browser→service→provider, no full before/after safety/audit evidence; tests absent from work branch |
| `UAT-RPT-002` | `tests/reports/test_generate_execution_characterization.py::test_scope_readiness_honors_scope_contract_without_stale_inventory_counts` — work branch | **PARTIAL SUB-INVARIANT**: report source-scope readiness returns false when a required cluster or Object Storage source is missing | No invalid report format/catalog submission, forged direct POST, rejection without job/report row or wrong-source fallback and no-false-success UI |
| `UAT-RPT-005` | `tests/contracts/reports/test_generated_reports_final_audit_20260815_contract.py::test_generated_registry_actions_are_permission_aware` — work branch | **SOURCE-CONTRACT ONLY**: Generated template actions are conditional on `reports.generate` and `reports.manage_storage` permissions | No unauthorized direct detail/download request proving HTTP denial and absence of artifact bytes, token, link or scoped metadata |
| `UAT-RPT-007` | `tests/contracts/reports/test_generated_reports_final_audit_20260815_contract.py::test_generated_registry_polling_is_filter_scoped_and_preserves_operator_selection` — work branch | **SOURCE-CONTRACT ONLY**: Generated registry filtering/polling template/service source checks, not actual Reports browser pagination or action completion | No Generated/Templates/Schedules/Storage browser clicks, paginated bounded server state, detail handoff or real artifact access. `tests/ui/test_representative_interactions.py::test_representative_filter_pagination_and_form_controls` explicitly exercises **Notification Center**, so it is not Reports evidence |

**Source review accounting:** 14 original + 9 newly inspected scenario IDs = **23/91 with limited assertion-level source review**; the other **68/91 are not yet individually audited at this level**. This is distinct from the four #1728 pilot manifest references, which are proposed mappings but **not run**, and from complete scenario-to-node-to-runtime acceptance, which remains **0/91 verified**. All **91** execution outcomes remain `NOT RUN` and human decisions remain `PENDING` at this checkpoint.

**Sequencing:** reconcile the normative #1725 QA contract before integration; use #1726 for browser ownership, #1727 for non-UI negative safety and #1728 for execution artifact admission. For review-only Tenant assertions, re-check the exact admitted staging source before treating the nodes as executable. Do not move code from `kaori/review/staging-uat` into this work branch during #1710's independent admission.

## Prioritized implementation decisions

1. **#1726 UI:** add real browser interaction paths for previously missed workflow states: Tenant Discovery/Adoption stale submit and Allocation modal, forbidden Secret Reveal, Generate Report wizard (worker completion/failed state), provider invalid validation, and form-modal validation at small-mobile size. Include post-interaction screenshots, geometry, keyboard/focus and backend state. Reuse `tests/ui/` harness and #543 visual source; no second runner or new baseline without review.
2. **#1727 non-UI:** close transactional/provenance gaps for stale provider reconciliation, unauthorized direct role/Secret requests, report job/storage failures, archive verification/cleanup guard and isolated mismatched release preflight. Differentiate fake provider/SQLite fixture from real production-like provider and governed sandbox proof.
3. **#1728 evidence integrity:** do not count a static test node as a user journey; link scenario → actual test node(s) → executed result and artifact → candidate SHA/tree/digest (when relevant). Mandatory SKIP/NOT RUN cannot become PASS.
4. **#1730 pilot:** real-provider and host UAT only after exact admitted staging candidate exists and scope is authorized; human reviewer records independent acceptance.
5. **After staging sync:** reconcile the three source-only test files with the accepted source and rerun mapping; this audit is version-scoped and must not be automatically promoted as evidence for a new source tree.

## Summary and limitations

At this source-inspection checkpoint, **9** cases have inspected partial behavioral/related component coverage; **5** have only source-contract or adjacent component evidence for the specific full scenario. **0/14** are confirmed automated end-to-end UAT PASS and **0/14** have recorded human acceptance in this audit. These are audit classifications, not a claim that no other existing test anywhere in the repository could provide more coverage.

## Work-branch implementations added after this source audit (NOT RUN)

The initial mapping above inspected the **review candidate** before these bounded changes. The following independent issue branches now contain additional source assertions; neither changes the historical audit category or provides an execution/UAT verdict:

| Scenario and issue | Work branch / source evidence | What was added | What is still not proven |
| --- | --- | --- | --- |
| `UAT-AUT-002` / #1727 | `kaori/task-1727-negative-session-regression`, `tests/access/authentication/test_login_characterization.py` | Flask-client invalid credentials cause no admitted session and the same client is redirected when requesting a protected page | No wrong-password **real browser** negative flow; no actual execution result |
| `UAT-RPT-003` / #1727 | `kaori/task-1727-negative-session-regression`, `tests/reports/test_generate_execution_characterization.py` | Isolated SQLite storage-unavailable preflight returns failure, produces no Report row, and refuses to evaluate a downstream report specification | Queue/worker dispatch-failure, storage outage after queuing and user-visible Generated Reports error/retry remain unproven |
| `UAT-UIX-002` / #1726 | `kaori/task-1726-interactive-ui-acceptance`, `tests/ui/test_accessibility_disclosures.py` and `tests/ui/test_representative_interactions.py` | Real UI validation error fields/text and post-HTMX clicked Notification Deck geometry/focus checked at canonical viewports | Real **mutation form** dialog with invalid data, error, saved/unchanged state and modal geometry in one flow remains outstanding |
| `UAT-UIX-006` / #1726 | `kaori/task-1726-interactive-ui-acceptance`, `tests/ui/conftest.py` + `tests/ui/test_representative_interactions.py` | Fixture preserves submitted request filters/Rows; browser selects status, Rows=10 and clicks Clear Filters through real HTMX, asserting reset and retained Rows | Isolated empty-state fixture is not proof of nonempty/paginated production data or runtime provider UAT |

**Execution status:** all entries above **SOURCE IMPLEMENTED / NOT RUN**. Actual pytest/Playwright and GitHub Actions remain deferred at maintainer request; exact test results cannot be inferred from committed source. Update this audit and execution records only after a targeted test is run on a named candidate. Full-scale route and scenario coverage remains to be inventoried.


## Work-branch implementation checkpoint — Tenant/Reports failure paths and UI search

The following source additions extend the work-branch implementation notes above. Their assertions have been inspected after commit, **not executed**. Their scenario status remains **NOT RUN**, and they do not replace end-to-end UAT.

| Scenario | Issue / candidate test | Source-implemented proof | Still outstanding |
| --- | --- | --- | --- |
| `UAT-TEN-004` | #1727 — `tests/kubernetes/tenant/test_capacity_governance.py::test_preflight_must_be_rechecked_after_capacity_headroom_changes` | The same proposed allocation is allowed against the original committed headroom but rejected against new committed commitments; asserts projected resource shortfalls and block decision | Must prove the owning *mutation submit* re-evaluates fresh committed evidence and prevents database/ResourceQuota writes after stale preview; actual Kubernetes read-back requires sandbox |
| `UAT-RPT-003` | #1727 — `tests/reports/test_generate_execution_characterization.py::test_report_enqueue_failure_records_failed_outcome_and_never_claims_queued` | Authenticated HTTP POST with isolated dispatch failure asserts failed-report marking, error Activity event/metadata and redirect to failed report detail rather than a false queued event | Actual worker/storage post-queue failure, persisted JobExecution/Report state, Report detail UI and browser trace; mocks are service/route proofs, not real worker UAT |
| `UAT-UIX-006` | #1726 — `tests/ui/test_representative_interactions.py::test_representative_filter_pagination_and_form_controls` (extended) | Playwright types a search term, checks it survives HTMX replacement, clicks Clear Filters and checks reset; captures filtered-state screenshot under canonical viewports | Nonempty notification data, pagination across several pages and real application/data integration |

The branch links remain:
- [UI implementation #1726](https://github.com/OXY7O/KAORI/tree/kaori/task-1726-interactive-ui-acceptance)
- [Non-UI implementation #1727](https://github.com/OXY7O/KAORI/tree/kaori/task-1727-negative-session-regression)
- [Scenario catalog / review #1738](https://github.com/OXY7O/KAORI/issues/1738)

**No CI/CD workflow, pytest or Playwright run is implied by these commits.** Release gates remain on hold by maintainer request.


## Work-branch implementation checkpoint — mutation submit and durable report failure

The following additions address the next gaps in #1727 **without a running provider, browser, or CI**. They are **SOURCE IMPLEMENTED / NOT RUN**, not accepted UAT evidence:

| Scenario | Source test | Specific invariant asserted | Remaining scope |
| --- | --- | --- | --- |
| `UAT-TEN-004` | `tests/kubernetes/tenant/test_capacity_governance.py::test_namespace_allocation_submit_rechecks_committed_capacity_before_provider_write` | Calls actual `change_native_namespace_allocation_committed` using an isolated Tenant/Namespace/profile and a fresh committed-capacity fixture. Previously accepted preview becomes insufficient after other commitments; the real `enforce_existing_namespace_allocation_preflight` logic rejects submit. The test verifies no provider reconciliation calls, no changed profile/quota on the original Namespace record, and bounded negative decision/rollback semantics. | The decision persistence and provider adapter are stubbed; prove real transaction/audit evidence and Kubernetes ResourceQuota no-write by disposable provider read-back in governed #1730 UAT. |
| `UAT-RPT-003` | `tests/reports/test_generate_execution_characterization.py::test_queued_report_failure_persists_failed_detail_without_pending_poll` | Persists a disposable Report row, invokes the real `mark_report_queue_failure` repository function, reloads it from a fresh SQLite DB session, and calls the real `get_report_detail_payload` controller with isolated serializer/lookup dependencies. Asserts durable `failed` status, error evidence, absent artifact, absent JobExecution identity, and disabled pending polling. | The detail serializer/artifact readiness are stubbed. No real worker or actual browser error/detail screenshot is proven. For a queue failure before dispatch, **no JobExecution** is an acceptable truthful state; do not fabricate one. |

These extend earlier unit/route checks without rewriting `UAT-TEN-004` or `UAT-RPT-003` to PASS. A denied preflight may itself record a capacity decision; that is **not** an applied Namespace quota mutation. For real provider UAT, independently verify no provider-side writes and no false-success Activity event. For Reports, distinguish queue admission failure from later running-worker failure (which may have a JobExecution).

Reviewer feedback entry point remains [#1738](https://github.com/OXY7O/KAORI/issues/1738); submit the scenario ID and expected UI/committed/provider/audit outcome. The existing GitHub Project taxonomy and human acceptance contract remain authoritative.


## Work-branch implementation checkpoint — browser Reports failure and isolated provider read-back

Both enhancements reuse owning suites. They are **source-implemented assertions** and remain **NOT RUN** under the maintainer CI/CD hold.

| Scenario | Work branch / test node | New verification at source level | Coverage boundary |
| --- | --- | --- | --- |
| `UAT-RPT-003` | #1726 / `tests/ui/test_representative_interactions.py::test_failed_generated_report_detail_is_truthful_and_responsive` | A real authenticated Playwright browser opens the actual `reports.generated_report_detail` route, rendering KAORI's existing Jinja detail template against a controlled failed-report payload. It checks failed Generation Note and error message, absent download/regenerate actions, absent false JobExecution, no automatic active polling, responsive action/viewport geometry, and captures light/dark screenshots across the six canonical viewport fixtures. | The application **presentation is real** but the report detail payload is simulated by a fixture. It does **not** prove live report database/worker failure, a full Generate wizard interaction, provider artifact read-back or human design acceptance. |
| `UAT-TEN-004` adjacent safety | #1727 / `tests/kubernetes/tenant/test_allocation_cutover.py::test_live_hash_change_blocks_cutover_before_provider_mutation` (extended) | Existing adopted-Native allocation cutover rejection now checks that no Namespace patch or quota/LimitRange creation occurred, and explicitly reobserves the unchanged fake-provider allocation identity after the rejection. | This is an **isolated fake Kubernetes API** and a *stale provider hash* boundary, complementary to the overbudget submit-preflight test. It is **not** proof of real ResourceQuota provider no-write after capacity rejection; authorized sandbox UAT remains required. |

**Evidence rule:** screenshot/trace creation when a test eventually executes is not proof that an artifact currently exists. The scenario still requires runtime JUnit, actual screenshot/trace, named candidate source SHA/tree, and independent human acceptance. If backend/visual source changes, map actual executed scenario results to the new candidate without inheriting old PASS.


## Cross-branch execution readiness — #1726 + #1728 (not admitted)

The new #1728 [stacked evidence work branch](https://github.com/OXY7O/KAORI/tree/kaori/task-1728-uat-execution-evidence) is **based on this #1738 scenario-catalog branch**, not on current `kaori/staging`. It contains a **manual** JUnit + browser artifact evidence evaluator, four selected scenario mappings and contract tests for incomplete/skip/failure/wrong candidate/missing evidence. The first-wave executor and reviewer guide live in [`docs/engineering/uat/EXECUTION.md`](https://github.com/OXY7O/KAORI/blob/kaori/task-1728-uat-execution-evidence/docs/engineering/uat/EXECUTION.md). **No automatic CI trigger/gate or Human Acceptance decision** is introduced.

Also implemented on separate #1726 [UI work branch](https://github.com/OXY7O/KAORI/tree/kaori/task-1726-interactive-ui-acceptance):

- **`UAT-RPT-003`:** `test_reports_generate_wizard_negative_submission_is_scoped_and_reviewable` interacts with the actual Reports Generate wizard (report type/name, required cluster validation, namespace, output format, Next/Review/Submit) using isolated service/worker/storage fixtures. It asserts that a controlled rejected request never becomes a false accepted report. The real worker and persisted artifact path remain unverified.
- **`UAT-TEN-004`:** `test_tenant_allocation_change_rejected_submit_records_no_provider_write` clicks/selects the actual Tenant Allocation Change form and submits via the real Flask route, with a stubbed capacity-rejected service and captured failure Activity event. The form is rendered in isolation for browser control; it is not whole-page visual UAT and makes **no live Kubernetes provider mutation or read-back claim**.

The #1728 manifest references these test node IDs alongside existing non-UI tests. It requires six canonical viewport JUnit cases for each browser node plus **separate screenshot and trace files by test node and viewport**. `UAT-TEN-004` remains blocked for complete real-provider acceptance when only simulated evidence exists.

**Every scenario mentioned here remains SOURCE IMPLEMENTED / NOT RUN on the unmerged source branches.** When #1725 standard, #1738 catalog, #1726 browser tests and #1727 non-UI tests are integrated, record the exact candidate SHA/tree/digest and execute only through the approved delivery/UAT workflow. Do not treat the existence of manifest/test files as a machine or human PASS.


## Exact pilot manifest-to-test traceability — 2026-10-16

**Scope:** #1738 read-only source audit of the four **planned** #1728 pilot IDs, with #1725's normative `docs/TESTING.md` record fields. The referenced #1728 manifest is located at `docs/engineering/uat/scenario_execution_manifest.json` on branch `kaori/task-1728-uat-execution-evidence`, which is stacked on #1738. **Neither the #1726 Playwright tests nor the #1727 non-UI tests are integrated into this #1738 work branch or the #1728 evidence branch.** This is a cross-branch traceability audit, not a runnable combined candidate or completed acceptance mapping.

The **seven exact node IDs** below were checked by reading their source on the named owning work branches. Assertions are characterized at their actual scope; path existence and a manifest entry are not test execution.

| Selected scenario | Exact inspected pytest / Playwright node | Owning branch | Assertion proved by source inspection | Missing scenario evidence |
| --- | --- | --- | --- | --- |
| `UAT-AUT-002` | `tests/access/authentication/test_login_characterization.py::test_invalid_credentials_return_generic_failure_without_account_disclosure` | #1727 | Flask client POST with invalid credentials; generic feedback and failure audit recording under stubbed authentication | Real browser wrong-password submission, protected-route access denial, session persistence/CSRF and trace on exact candidate |
| `UAT-UIX-006` | `tests/ui/test_representative_interactions.py::test_notification_center_filters_and_rows_survive_htmx_reset` | #1726 | Authenticated browser selects Notification Center status, receives HTMX responses, changes Rows 5→10, uses Clear Filters, preserves Rows, tests viewport fit | Actual six-viewport execution/JUnit/screenshots/traces; other app registry filters are outside this one scenario's browser coverage |
| `UAT-RPT-003` | `tests/reports/test_generate_execution_characterization.py::test_queued_report_failure_persists_failed_detail_without_pending_poll` | #1727 | Isolated SQLite Report request, queue failure persisted as `failed`, no artifact or JobExecution ID and no active detail polling after re-read | This is **pre-dispatch queue failure**, not proof of a running-worker/storage write failure, real worker or actual artifact store |
| `UAT-RPT-003` | `tests/ui/test_representative_interactions.py::test_failed_generated_report_detail_is_truthful_and_responsive` | #1726 | Browser renders actual Generated detail template with injected failed payload, hides download/regenerate, checks absent JobExecution/polling and responsive light/dark output | Fake detail payload, no live failed job, DB-backed browser flow or artifact storage read-back |
| `UAT-RPT-003` | `tests/ui/test_representative_interactions.py::test_reports_generate_wizard_negative_submission_is_scoped_and_reviewable` | #1726 | Browser visits Reports Generate, selects report/scope/format, validates required cluster and traverses Review/Submit; stubbed enqueue rejects with user-visible feedback | **Adjacent queue-admission rejection**, not an injected renderer/worker/storage failure; rejection service is stubbed, no persisted no-write proof |
| `UAT-TEN-004` | `tests/kubernetes/tenant/test_capacity_governance.py::test_namespace_allocation_submit_rechecks_committed_capacity_before_provider_write` | #1727 | Real service uses **stubbed** current capacity showing a previously allowed preview is now over budget; blocks submit, preserves Namespace record fields and does not invoke stubbed provider writes | Stubbed DB/provider cannot establish actual ResourceQuota/LimitRange no-write, persisted Activity or Kubernetes before/after state |
| `UAT-TEN-004` | `tests/ui/test_representative_interactions.py::test_tenant_allocation_change_rejected_submit_records_no_provider_write` | #1726 | Browser selects real rendered allocation form and submits, but route service is **stubbed** to reject; captures failure Activity payload and no recorded success | Isolated form not entire Tenant page; missing real committed-state and provider read-back. CSRF is disabled only in the isolated test fixture |

**Explicit #1728 manifest obligations (source review, not delivered artifacts):**
- **Four** selected scenario IDs, **seven** pytest node mappings (3 non-UI, 4 browser). Each browser node declares the existing six viewport IDs `large-desktop`, `laptop`, `compact-laptop`, `tablet`, `mobile`, `small-mobile`; the #1726 `tests/ui/conftest.py` fixture has matching IDs.
- A complete manifest-run JUnit would need **27** node/viewport outcomes (3 non-UI + 24 browser variants), with **24 independently attributable screenshot artifacts and 24 trace artifacts**. These are required evidence counts, **not files currently produced**.
- `UAT-TEN-004` additionally requires independently reviewable `provider_readback`, `committed_state` and `activity_audit` JSON evidence for the selected source SHA/run identity. **Real-provider confirmation and a human decision are mandatory** even if all isolated fixture tests later PASS.
- The standalone #1728 evaluator can flag **NOT RUN, SKIP, missing/wrong-candidate evidence**, but cannot authenticate provider reality by itself or grant human acceptance. Its source must be reconciled with #1725's normative version and the exact admitted staging tree.
- Additional **partially inspected** scenario `UAT-UIX-006` raises the source-reviewed ID inventory from **23/91 to 24/91**. The other three manifest scenarios (`UAT-AUT-002`, `UAT-RPT-003`, `UAT-TEN-004`) were already in the original 14 reviews and are **not counted again**. **67/91** IDs still lack individual assertion-level review.

**Integration prerequisite:** converge reviewed #1725 documentation, #1738 specifications, #1726 browser tests, #1727 non-UI tests and #1728 pilot evidence tooling on one issue-linked source candidate **before** executing the existing Developer Check/Full Admission/UAT flow. No PR, merge, CI gate, live provider or deployment is authorized by this source mapping. All **91/91** scenario results remain **NOT RUN**, all human decisions **PENDING**, and admission **HOLD**.

## Welcome Workspace Catalog source-mapping addendum — 2026-10-24

**Authority:** #1738 catalog specification, #746 Welcome UAT evidence, #1726 UI, #1727 non-UI and #1725 evidence fields. The 2026-10-16 original **24/91** individually reviewed assertion IDs remain a historical checkpoint. The seven additional written IDs extend the catalog to **98**; the matrix's **24/98** source-reviewed original IDs / **74/98** awaiting individual audit deliberately do **not** recast preliminary source pointers as complete scenario mappings.

**Source inspected:** `kaori/review/staging-uat` Welcome routes/shortcuts, Access Overview/decorator, `tests/e2e/welcome/test_welcome_smoke.py`, `tests/welcome/test_welcome_characterization.py`, `tests/security/welcome/test_welcome_security.py`, and `tests/ui/test_representative_interactions.py`. These paths are on a separate review holding branch, not proof of an identical frozen candidate in this staging-based #1738 work branch.

| Scenario | Existing source-level candidate | Missing exact-candidate assertion |
| --- | --- | --- |
| `UAT-WEL-001` | Authenticated `/` and `/welcome` E2E smoke; `app/welcome/routes.py` | Attributable execution/response evidence; provider-free boundary as real integration observation |
| `UAT-WEL-002` | Welcome shortcut characterization and security metadata filtering | Default Viewer **server-rendered HTML** negative check, all effective grants/card count and forbidden HTML absence |
| `UAT-WEL-003` | `test_welcome_catalog_content_search_and_card_geometry_across_canonical_viewports` | Exact-candidate browser run and stored post-filter artifact |
| `UAT-WEL-004` | Same Playwright test checks Escape after `tenant` filter; template/JS empty state contracts | Browser **unmatched** query yields 0 and canonical empty state, then Escape restores original permissions/count |
| `UAT-WEL-005` | `test_welcome_visual_qa_light_and_dark` and `tests/ui/visual_audit.py` | Complete exact-candidate 6×2 run, full-catalog scroll/action assertions and reviewed baseline diff |
| `UAT-WEL-006` | `tests/unit/welcome/test_welcome_target_resolution.py` | Real browser Open Workspace click-through, correct route and independent authorization assertion |
| `UAT-IAM-007` | `app/access/overview/routes.py` guarded by `any_permission_required`; decorator aborts 403 | Automated authenticated Viewer GET `/access/` response status, safe 403 HTML/no protected content |

**Manual evidence boundary:** #746 records 2026-10-24 operator-observed `tenant` filtering, unmatched-query empty state, Escape reset, Viewer role-aware counts, real browser `GET /access/` HTTP **403**, and mobile light/dark screenshots at 390×844 and 360×800. Those observations support bounded human UAT only; none is retroactively a pytest/Playwright machine PASS for a newly written Scenario ID. The exact local SHA was not supplied.

**Next automation work:** Reuse #1726 Playwright and #1727 capability-owned security/test-client suites; extend existing tests for the specific uncovered browser/HTML/authorization assertions rather than adding a Gherkin runner, bespoke verifier or extra Visual QA baseline engine. Any new test change needs issue-linked work and reviewed branch targeting; keep official CI/CD, Full Admission, staging/main promotion and release **HOLD**.
