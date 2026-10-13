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
