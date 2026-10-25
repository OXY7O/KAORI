# KAORI UAT — All-Scenario Written Specification & Execution Coverage Matrix

**Issue authority:** #1738 catalog, #1726 UI, #1727 non-UI, #1728 execution evidence, #1730 real UAT and human acceptance.

**Checkpoint 2026-10-16 (original 91 cases):** Written specifications remain unchanged. Nine supplemental IDs plus the #1728 four-scenario pilot manifest were inspected against actual source assertions in their separate #1726/#1727 branches. No integrated exact candidate, machine scenario execution or human UAT acceptance is proven. CI/CD, PR and merge remain on hold.

**#3012 implementation checkpoint (separate branch; NOT RUN):** Four missing assertions for WEL-002/004/006 and IAM-007 now have authored Flask/Playwright test nodes on `kaori/issue-3012-welcome-qa-regressions`. These are not executed, merged or an admission result. Original limited-source-audit numerator 24 remains unchanged pending test-node assertion and runtime review.

**Addendum 2026-10-24:** Six Welcome-owned scenarios (`UAT-WEL-001`–`006`) and one separate IAM Viewer direct-read denial (`UAT-IAM-007`) expand the written catalog to 98. Their links to existing source assertions are preliminary, not complete exact-candidate test-node coverage or machine PASS. Human Welcome acceptance/screenshot observations remain recorded on #746, not retrospectively attributed to these new Gherkin IDs.

**Kubernetes Admin addendum (2026-10-24):** #2605 records explicit operator Human Acceptance for the bounded manually executed Batch 01–06 (navigation, pager, filters, Cancel, authorized Harbor save/rollback, Activity Audit correlation, Viewer GET denial). These are issue-bound manual results, **not** machine `UAT-LIF-*` PASS verdicts; the matrix still says `NOT RUN / PENDING` per scenario because no exact ID-to-JUnit/Playwright execution record was produced. Direct POST/CSRF negative, unavailable-provider failure, Error detail visual, and full six-viewport × two-theme matrix were **not** exercised.

**Kubernetes Dashboard human acceptance (2026-10-24):** #937 documents an explicit operator **Human UAT APPROVED** decision over the four Dashboard tabs plus a downloadable Ready report. The ten new `UAT-KDB-001`–`010` specifications provide capability-owned reusable requirements. Their source/test mappings below are provisional; **no per-Scenario-ID exact-candidate execution record exists**, and the approved UI screenshots do not establish negative scope/RBAC/failure outcomes or the full six-viewport/two-theme automated Visual QA. This acceptance is recorded on the **owning issue**, not silently in the machine-result column.

**Operations Center UAT addendum (2026-10-25; #3115):** Operator accepted the bounded Jobs Configuration, Data Lifecycle and Operations Overview visual/function paths after incremental screenshot feedback. Previous operator tests included 29 focused Jobs/Lifecycle pytest PASS with Platform Operations Final Lock v2.2 93 templates PASS on an earlier candidate; the final Overview refinement received 9 focused pytest PASS, djLint PASS and Ruff check/format PASS. This is **human UI acceptance**, not 13 newly attributed machine Scenario-ID PASS results. No exact-ID browser trace/role-fault synthetic run was supplied. Guarded recovery/provider mutations, negative cross-permission tests, intentional disabled features and full responsive matrix remain **NOT RUN / BLOCKED as applicable**. Official Developer Check, Full Admission, staging/main promotion HOLD.

**Kubernetes TLS Rotation human UAT (2026-10-25; #3107/#3116):** The operator accepted the bounded single-rotation negative/positive workflow and revised Bulk TLS confirmation UI. Evidence includes single Secret fingerprint provider read-back, both certificate mismatch and SAN negatives, two-target bulk validation, updated modal screenshot, `djlint --check` PASS and **8 presentation contract pytest PASS** on holding SHA `4f5f098214d40296037ad6e941f65626c8ad0df4`. New `UAT-KOP-006`–`009` author precise reusable requirements. **Bulk apply/provider read-back, no-PATCH keyboard dismissal, file/target invalidation, full viewport/theme matrix and security fault injection are NOT RUN by Scenario ID.** No machine scenario PASS is inferred; full admission HOLD.

**Object Storage Dashboard #3168 (2026-10-25):** Ten UAT-OSD-001..010 reusable specs added. Operator visual acceptance of four tabs and prior 52 focused pytest PASS / Ruff+dJlint / later Ruff format PASS do not make exact-ID Scenario PASS. Report generation/download, RBAC, faulty source, multi-system negatives and full theme/mobile remain NOT RUN; all admission HOLD.

## Coverage accounting

| Measure | Grounded assessment |
| --- | --- |
| Written case procedures | **143/143** across 21 Gherkin files and case register |
| Preserved original first-wave | **14**; source mapping audit partial only |
| Scenario IDs with inspected source assertions | **24/143** of the original IDs (14 first-wave + 9 supplemental + UIX-006); 7 new IDs have preliminary source pointers but no complete scenario audit |
| Scenario IDs without individual assertion-level review | **119/143**; includes 13 newly authored Operations Center IDs and does not prove equivalent tests are absent |
| Newly expanded for domain-owner review | **129**; not yet approved by owning capability |
| IDs referenced by the #1728 pilot execution manifest | **4/143**, source references, NOT RUN |
| Remaining #1728 pilot execution-manifest mapping | **139/143 not selected** into four-case pilot; independent of 24 assertion reviews, not proof equivalent tests are absent |
| Confirmed full machine UAT PASS | **0/143 attributed to this catalog checkpoint** |
| Human acceptance | **0/143 attributed to this catalog checkpoint; manual #746 acceptance is recorded separately** |

**Mapping vocabulary:** The nine `source audit` entries document specific inspected assertions, not completed scenario-to-node coverage. `REVIEW-ONLY` means the named tests were present on `kaori/review/staging-uat` but missing from this staging-based branch. Read the [assertion audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md) for exact test node IDs and limitations. Four #1728 pilot manifest references include seven exact test nodes verified in their **separate** owning source branches; these remain **NOT RUN**, not four passing UAT scenarios. See [pilot manifest-to-test traceability](../KAORI_UAT_TEST_MAPPING_AUDIT.md#exact-pilot-manifest-to-test-traceability--2026-10-16).

**Admission:** HOLD. Before invoking existing gates, reconcile owner-reviewed requirements, actual browser/API/node assertions, authorized provider evidence and exact candidate. Unsupported/unadmitted operations remain BLOCKED, not PASS. This document does not define a new CI gate.

## Per-scenario review

| Scenario ID | Risk | Layer | Specification | Test-node mapping | Execution |
| --- | --- | --- | --- | --- | --- |
| `UAT-AUT-001` | High | Both | [Gherkin](features/aut-authentication-sessions.feature) | ADJACENT source audit: login GET/render; no valid-login/session UAT ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-AUT-002` | High | Both | [Gherkin](features/aut-authentication-sessions.feature) | Pilot #1728: invalid-credential Flask test exists #1727; missing browser protected-route/session proof ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-AUT-003` | High | Non-UI | [Gherkin](features/aut-authentication-sessions.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-AUT-004` | High | Both | [Gherkin](features/aut-authentication-sessions.feature) | SOURCE-CONTRACT audit: CSRF markup/route; rejected mutation unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-AUT-005` | Medium | UI | [Gherkin](features/aut-authentication-sessions.feature) | SOURCE-CONTRACT audit: POST logout route; browser Back/session revoke unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-IAM-001` | High | Both | [Gherkin](features/iam-access-rbac.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-IAM-002` | High | Both | [Gherkin](features/iam-access-rbac.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-IAM-003` | High | Non-UI | [Gherkin](features/iam-access-rbac.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-IAM-004` | Medium | UI | [Gherkin](features/iam-access-rbac.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-IAM-005` | High | Both | [Gherkin](features/iam-access-rbac.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-IAM-006` | Medium | UI | [Gherkin](features/iam-access-rbac.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-IAM-007` | High | Both | [Gherkin](features/iam-access-rbac.feature) | SOURCE AUTHORED / NOT RUN: #3012 `tests/e2e/welcome/test_welcome_smoke.py::test_viewer_direct_access_overview_returns_http_403_and_safe_guidance`; separate review-based branch | NOT RUN / PENDING |
| `UAT-KCL-001` | High | Both | [Gherkin](features/kcl-kubernetes-clusters.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KCL-002` | High | Both | [Gherkin](features/kcl-kubernetes-clusters.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KCL-003` | High | Non-UI | [Gherkin](features/kcl-kubernetes-clusters.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KCL-004` | High | Both | [Gherkin](features/kcl-kubernetes-clusters.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KDB-001` | High | UI | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: authenticated Dashboard E2E smoke + source-qualified operational KPI contracts; full candidate scope not individually audited | NOT RUN / PENDING |
| `UAT-KDB-002` | High | Both | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: health table/pagination contract and source-derived severity; registered Healthy vs alert Critical semantics require committed fixture | NOT RUN / PENDING |
| `UAT-KDB-003` | Medium | Both | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | SOURCE REVIEW + LOCAL QA: capacity/forecast contract + Kubernetes domain unit (36 passed combined dashboard suite at historical SHA; not Scenario-ID execution) | NOT RUN / PENDING |
| `UAT-KDB-004` | High | UI | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: five AlertCase preview and shared six-step response contracts; real alert lifecycle fixture per Scenario-ID missing | NOT RUN / PENDING |
| `UAT-KDB-005` | Medium | UI | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | SOURCE REVIEW + LOCAL QA: shared 2-line recommendation contract and CSS verifier; operator screenshot accepted; hover/detail interaction not proven | NOT RUN / PENDING |
| `UAT-KDB-006` | High | Both | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | MANUAL ACCEPTED ON #937: operator opened Reports Workspace and downloaded one Ready Analytics Overview Report; no full per-ID automation or checksum proof | NOT RUN / PENDING |
| `UAT-KDB-007` | Medium | UI | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: shared tab/Visual QA source contracts; full 6×2 light/dark and browser history test not attributed to this ID | NOT RUN / PENDING |
| `UAT-KDB-008` | High | Both | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: unavailable alert and dashed empty-state source contract; missing-data negative fixture not operator-executed | NOT RUN / PENDING |
| `UAT-KDB-009` | High | Both | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: selected-cluster resolution, clusterless blocker and Kubernetes-only report-domain contract; multi-cluster negative runtime unverified | NOT RUN / PENDING |
| `UAT-KDB-010` | High | Both | [Gherkin](features/kdb-kubernetes-operations-dashboard.feature) | REVIEW-ONLY: dashboard authorization-first Flask characterization tests; restricted direct browser/endpoints not operator-executed | NOT RUN / PENDING |
| `UAT-INV-001` | Medium | UI | [Gherkin](features/inv-kubernetes-inventory.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INV-002` | High | Both | [Gherkin](features/inv-kubernetes-inventory.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INV-003` | High | Non-UI | [Gherkin](features/inv-kubernetes-inventory.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INV-004` | Medium | UI | [Gherkin](features/inv-kubernetes-inventory.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INV-005` | High | Both | [Gherkin](features/inv-kubernetes-inventory.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KAN-001` | Medium | Both | [Gherkin](features/kan-kubernetes-analytics.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KAN-002` | High | Both | [Gherkin](features/kan-kubernetes-analytics.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KAN-003` | High | Non-UI | [Gherkin](features/kan-kubernetes-analytics.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KAN-004` | Medium | UI | [Gherkin](features/kan-kubernetes-analytics.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-GOV-001` | High | Both | [Gherkin](features/gov-kubernetes-governance.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-GOV-002` | High | Both | [Gherkin](features/gov-kubernetes-governance.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-GOV-003` | High | Non-UI | [Gherkin](features/gov-kubernetes-governance.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-GOV-004` | Medium | UI | [Gherkin](features/gov-kubernetes-governance.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-TEN-001` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-TEN-002` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-TEN-003` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | PARTIAL source audit: capacity preflight only; create/provider read-back unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-TEN-004` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | Pilot #1728: stale capacity rejection #1727 + isolated form #1726; real-provider read-back mandatory ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-TEN-005` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-TEN-006` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | PARTIAL REVIEW-ONLY audit: rollback; provider-patch/commit failure not fully proven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-TEN-007` | Medium | UI | [Gherkin](features/ten-kubernetes-tenant.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-TEN-008` | High | Both | [Gherkin](features/ten-kubernetes-tenant.feature) | PARTIAL REVIEW-ONLY audit: foreign ownership; generation replay unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-KOP-001` | High | Both | [Gherkin](features/kop-kubernetes-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KOP-002` | High | Both | [Gherkin](features/kop-kubernetes-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KOP-003` | Medium | UI | [Gherkin](features/kop-kubernetes-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KOP-004` | High | Both | [Gherkin](features/kop-kubernetes-operations.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-KOP-005` | High | Non-UI | [Gherkin](features/kop-kubernetes-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-KOP-006` | High | Both | [Gherkin](features/kop-kubernetes-operations.feature) | HUMAN SINGLE READ-BACK: screenshot, Kubernetes SHA-256 fingerprint PASS, validation code paths exist; no ID-specific pytest/Playwright result | NOT RUN / PENDING |
| `UAT-KOP-007` | High | Both | [Gherkin](features/kop-kubernetes-operations.feature) | HUMAN NEGATIVES: mismatched private key and uncovered SAN blocked; no exact-ID mutation-denial test result | NOT RUN / PENDING |
| `UAT-KOP-008` | High | Both | [Gherkin](features/kop-kubernetes-operations.feature) | HUMAN PARTIAL: 2 targets validated and scoped modal shown; BULK APPLY and provider read-back unobserved | NOT RUN / PENDING |
| `UAT-KOP-009` | Medium | UI | [Gherkin](features/kop-kubernetes-operations.feature) | HUMAN VISUAL ACCEPTED #3116; djlint PASS and 8 presentation pytest PASS at holding SHA 4f5f098; Cancel/Escape/backdrop/focus/invalidation not mapped per ID | NOT RUN / PENDING |
| `UAT-OSD-001` | High | UI | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-002` | High | Both | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-003` | Medium | Both | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-004` | Medium | Both | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-005` | High | UI | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-006` | Medium | UI | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-007` | High | Both | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-008` | Medium | UI | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-009` | High | Both | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OSD-010` | High | Both | [Gherkin](features/osd-object-storage-operations-dashboard.feature) | REVIEW-ONLY: Object Storage dashboard and shared family; exact-ID assertions/browser run not yet validated | NOT RUN / PENDING |
| `UAT-OST-001` | Medium | Both | [Gherkin](features/ost-object-storage.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OST-002` | High | Both | [Gherkin](features/ost-object-storage.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OST-003` | Medium | UI | [Gherkin](features/ost-object-storage.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OST-004` | High | Non-UI | [Gherkin](features/ost-object-storage.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REG-001` | High | Both | [Gherkin](features/reg-artifact-registry.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REG-002` | High | Both | [Gherkin](features/reg-artifact-registry.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REG-003` | High | Both | [Gherkin](features/reg-artifact-registry.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-REG-004` | Medium | UI | [Gherkin](features/reg-artifact-registry.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REG-005` | High | Non-UI | [Gherkin](features/reg-artifact-registry.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-ING-001` | High | Both | [Gherkin](features/ing-integrations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-ING-002` | High | Both | [Gherkin](features/ing-integrations.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-ING-003` | High | Non-UI | [Gherkin](features/ing-integrations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-ING-004` | Medium | UI | [Gherkin](features/ing-integrations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-ING-005` | High | Non-UI | [Gherkin](features/ing-integrations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-NTF-001` | Medium | Both | [Gherkin](features/ntf-notifications.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-NTF-002` | High | Non-UI | [Gherkin](features/ntf-notifications.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-NTF-003` | High | Both | [Gherkin](features/ntf-notifications.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-NTF-004` | Medium | UI | [Gherkin](features/ntf-notifications.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INL-001` | High | Both | [Gherkin](features/inl-intelligence.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INL-002` | High | Non-UI | [Gherkin](features/inl-intelligence.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INL-003` | High | Both | [Gherkin](features/inl-intelligence.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INL-004` | Medium | UI | [Gherkin](features/inl-intelligence.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-INL-005` | High | Non-UI | [Gherkin](features/inl-intelligence.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-RPT-001` | High | Both | [Gherkin](features/rpt-reports.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-RPT-002` | High | Both | [Gherkin](features/rpt-reports.feature) | PARTIAL source audit: source-scope readiness; invalid direct POST unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-RPT-003` | High | Both | [Gherkin](features/rpt-reports.feature) | Pilot #1728: queue-failure DB assertion #1727 plus two UI tests #1726; no real worker/storage fault proof ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-RPT-004` | Medium | UI | [Gherkin](features/rpt-reports.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-RPT-005` | High | Non-UI | [Gherkin](features/rpt-reports.feature) | SOURCE-CONTRACT audit: template permissions; direct download denial unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-RPT-006` | High | Non-UI | [Gherkin](features/rpt-reports.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-RPT-007` | Medium | UI | [Gherkin](features/rpt-reports.feature) | SOURCE-CONTRACT audit: Generated polling; Reports browser flows unproven ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-OPS-001` | Medium | Both | [Gherkin](features/ops-platform-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OPS-002` | High | Non-UI | [Gherkin](features/ops-platform-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OPS-003` | High | Both | [Gherkin](features/ops-platform-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OPS-004` | Medium | UI | [Gherkin](features/ops-platform-operations.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-OPS-005` | Medium | UI | [Gherkin](features/ops-platform-operations.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/test_platform_operations_overview_final_lock_contract.py; app/platform_operations/overview/presentation.py; #1633/#3110; Operator visually accepted Overview screenshot and one-line refinement; do not claim a machine Scenario-ID PASS | NOT RUN / PENDING |
| `UAT-OPS-006` | Medium | UI | [Gherkin](features/ops-platform-operations.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/jobs/test_job_configuration_catalog_search_a11y_contract.py; test_job_configuration_workspace_redesign_contract.py; #3090/#3102; Human UAT accepted the tested design/functions; disabled controls awaiting full feature cycle excluded | NOT RUN / PENDING |
| `UAT-OPS-007` | Medium | UI | [Gherkin](features/ops-platform-operations.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/jobs/test_job_configuration_workspace_redesign_contract.py; app/templates/platform_operations/jobs/configuration/definitions/report_schedule.html; #3090; Human accepted the visible channel presentation, not every scaled fixture | NOT RUN / PENDING |
| `UAT-OPS-008` | High | UI | [Gherkin](features/ops-platform-operations.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/jobs/test_job_configuration_workspace_redesign_contract.py; definitions/object_storage_inventory_sync.html; definitions/artifact_registry_inventory_sync.html; #3090; Presentation accepted; protected mutation flow not exercised in this batch | NOT RUN / PENDING |
| `UAT-OPS-009` | High | Both | [Gherkin](features/ops-platform-operations.feature) | SOURCE-OWNED / UNEXECUTED: app/platform_operations/jobs/configuration.py::build_job_configuration_attention_summary; app/platform_operations/overview/presentation.py; #1635; Not individually executed; do not mark Human Accepted negative path | NOT RUN / PENDING |
| `UAT-OPS-010` | High | Both | [Gherkin](features/ops-platform-operations.feature) | SOURCE-OWNED / UNEXECUTED: app/platform_operations/overview/routes.py; app/welcome/shortcuts.py; tests/contracts/platform_operations/test_platform_operations_overview_final_lock_contract.py; #1637; Not individually executed with restricted roles | NOT RUN / PENDING |
| `UAT-OPS-011` | High | Non-UI | [Gherkin](features/ops-platform-operations.feature) | SOURCE-OWNED / UNEXECUTED: tests/contracts/platform_operations/jobs/test_job_configuration_workspace_redesign_contract.py; owning storage/registry reconciliation tests; #1592/#3090; Not executed; only manual control appearance accepted | NOT RUN / PENDING |
| `UAT-OPS-012` | Medium | UI | [Gherkin](features/ops-platform-operations.feature) | HUMAN-OBSERVED / UNATTRIBUTED: app/templates/platform_operations/jobs/configuration/; #1592/#3090; Human accepted truthful disabled presentation; feature-cycle completion remains blocked | NOT RUN / PENDING |
| `UAT-LIF-001` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-LIF-002` | High | Non-UI | [Gherkin](features/lif-data-lifecycle.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-LIF-003` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-LIF-004` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED: #2605 Batch 01; exact machine ID execution NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-005` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-LIF-006` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED: #2605/#2457 bounded Batch 02–06; machine ID run NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-007` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED: #2605/#2457 bounded Batch 02–06; machine ID run NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-008` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED: #2605/#2457 bounded Batch 02–06; machine ID run NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-009` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED: #2605/#2457 bounded Batch 02–06; machine ID run NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-010` | High | Non-UI | [Gherkin](features/lif-data-lifecycle.feature) | SPECIFIED BACKLOG: negative/degraded/full visual matrix NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-011` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | SPECIFIED BACKLOG: negative/degraded/full visual matrix NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-012` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED: Access #1384 Warning/Success, Error detail visual NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-013` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | SPECIFIED BACKLOG: negative/degraded/full visual matrix NOT RUN | NOT RUN / PENDING |
| `UAT-LIF-014` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/test_data_lifecycle_domain_navigator_contract.py; app/templates/platform_operations/data_lifecycle/index.html; #3102/#2907; Human accepted visible navigation and footer; full viewport/theme matrix not individually recorded | NOT RUN / PENDING |
| `UAT-LIF-015` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/test_data_lifecycle_archive_reverify_contract.py; test_data_lifecycle_complete_uat_matrix_contract.py; #2907/#1569; Previous human Archive Only approval, not an inferred full-machine scenario PASS | NOT RUN / PENDING |
| `UAT-LIF-016` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | HUMAN-OBSERVED / UNATTRIBUTED: tests/contracts/platform_operations/test_data_lifecycle_history_filter_rows_contract.py; test_data_lifecycle_history_verify_browser_contract.py; #2907/#2972/#2974; Visual/functional acceptance of tested paths; explicit re-verification evidence remains separate | NOT RUN / PENDING |
| `UAT-LIF-017` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | SOURCE-OWNED / UNEXECUTED: app/templates/platform_operations/data_lifecycle/; tests/contracts/platform_operations/test_data_lifecycle_audit_event_operational_ui_contract.py; #2889/#2847; Deferred feature-cycle coverage, not end-to-end UAT | NOT RUN / PENDING |
| `UAT-LIF-018` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | SOURCE-OWNED / UNEXECUTED: tests/contracts/platform_operations/test_data_lifecycle_archive_reverify_contract.py; test_data_lifecycle_mutation_domain_contract.py; #1569/#2907; Unexecuted negative boundary; keep under QA/feature admission backlog | NOT RUN / PENDING |
| `UAT-WEL-001` | Medium | UI | [Gherkin](features/wel-welcome-workspace-catalog.feature) | REVIEW-ONLY: authenticated / and /welcome E2E smoke exists; provider-free source contract is partial | NOT RUN / PENDING |
| `UAT-WEL-002` | High | Both | [Gherkin](features/wel-welcome-workspace-catalog.feature) | SOURCE AUTHORED / NOT RUN: #3012 `tests/e2e/welcome/test_welcome_smoke.py::test_viewer_welcome_html_contains_only_permitted_workspace_cards`; separate review-based branch | NOT RUN / PENDING |
| `UAT-WEL-003` | Medium | UI | [Gherkin](features/wel-welcome-workspace-catalog.feature) | REVIEW-ONLY: Playwright Welcome catalog tenant-search test exists; exact candidate execution not observed | NOT RUN / PENDING |
| `UAT-WEL-004` | Medium | UI | [Gherkin](features/wel-welcome-workspace-catalog.feature) | SOURCE AUTHORED / NOT RUN: #3012 extends `test_welcome_catalog_content_search_and_card_geometry_across_canonical_viewports` with unmatched empty state and Escape restore | NOT RUN / PENDING |
| `UAT-WEL-005` | High | UI | [Gherkin](features/wel-welcome-workspace-catalog.feature) | REVIEW-ONLY: Playwright canonical Welcome 6-viewport x 2-theme baseline/geometry exists; full-scroll and contrast proof incomplete | NOT RUN / PENDING |
| `UAT-WEL-006` | Medium | UI | [Gherkin](features/wel-welcome-workspace-catalog.feature) | SOURCE AUTHORED / NOT RUN: #3012 `test_welcome_authorized_workspace_card_navigation_across_canonical_viewports` clicks permitted Settings; broader independently denied destination requires IAM read check | NOT RUN / PENDING |
| `UAT-UIX-001` | Medium | UI | [Gherkin](features/uix-shared-ui-ux.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-UIX-002` | High | UI | [Gherkin](features/uix-shared-ui-ux.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-UIX-003` | Medium | UI | [Gherkin](features/uix-shared-ui-ux.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-UIX-004` | High | UI | [Gherkin](features/uix-shared-ui-ux.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-UIX-005` | Medium | UI | [Gherkin](features/uix-shared-ui-ux.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-UIX-006` | Medium | UI | [Gherkin](features/uix-shared-ui-ux.feature) | Pilot #1728: HTMX filter/Rows/Clear Filters browser test exists #1726, six viewports; NOT RUN ([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md)) | NOT RUN / PENDING |
| `UAT-UIX-007` | High | UI | [Gherkin](features/uix-shared-ui-ux.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REL-001` | High | Non-UI | [Gherkin](features/rel-release-uat.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REL-002` | High | Non-UI | [Gherkin](features/rel-release-uat.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-REL-003` | High | Non-UI | [Gherkin](features/rel-release-uat.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-REL-004` | Medium | UI | [Gherkin](features/rel-release-uat.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |

## Closure before gate

1. Obtain domain-owner review of the 129 newly expanded written procedures against current approved KAORI standards and admitted source routes.
2. Map all 143 Scenario IDs to actually executable pytest/Playwright node IDs and check assertions, roles, fixtures and cleanup; source-only contracts are not browser/provider coverage.
3. Integrate #1725 standards, #1738 catalog, #1726 Playwright and #1727 non-UI test branches into a controlled exact candidate, including synchronizing the stacked #1728 branch with this updated #1738 tree.
4. After the explicit CI/CD hold is lifted, run Developer Check and admission as required, then governed UAT with JUnit, screenshot/trace, committed/provider read-back and a separate human decision.
5. Treat any mandatory SKIP/NOT RUN/FAIL, missing provider authorization, or misleading fake-provider PASS as unresolved. No automatic release readiness is inferred.

