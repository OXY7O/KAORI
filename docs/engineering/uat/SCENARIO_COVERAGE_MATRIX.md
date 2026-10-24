# KAORI UAT — All-Scenario Written Specification & Execution Coverage Matrix

**Issue authority:** #1738 catalog, #1726 UI, #1727 non-UI, #1728 execution evidence, #1730 real UAT and human acceptance.

**Checkpoint 2026-10-16 (original 91 cases):** Written specifications remain unchanged. Nine supplemental IDs plus the #1728 four-scenario pilot manifest were inspected against actual source assertions in their separate #1726/#1727 branches. No integrated exact candidate, machine scenario execution or human UAT acceptance is proven. CI/CD, PR and merge remain on hold.

**#3012 implementation checkpoint (separate branch; NOT RUN):** Four missing assertions for WEL-002/004/006 and IAM-007 now have authored Flask/Playwright test nodes on `kaori/issue-3012-welcome-qa-regressions`. These are not executed, merged or an admission result. Original limited-source-audit numerator 24 remains unchanged pending test-node assertion and runtime review.

**Addendum 2026-10-24:** Six Welcome-owned scenarios (`UAT-WEL-001`–`006`) and one separate IAM Viewer direct-read denial (`UAT-IAM-007`) expand the written catalog to 98. Their links to existing source assertions are preliminary, not complete exact-candidate test-node coverage or machine PASS. Human Welcome acceptance/screenshot observations remain recorded on #746, not retrospectively attributed to these new Gherkin IDs.

## Coverage accounting

| Measure | Grounded assessment |
| --- | --- |
| Written case procedures | **98/98** across 19 Gherkin files and case register |
| Preserved original first-wave | **14**; source mapping audit partial only |
| Scenario IDs with inspected source assertions | **24/98** of the original IDs (14 first-wave + 9 supplemental + UIX-006); 7 new IDs have preliminary source pointers but no complete scenario audit |
| Scenario IDs without individual assertion-level review | **74/98**; includes the 7 newly specified IDs and does not prove equivalent tests are absent |
| Newly expanded for domain-owner review | **84**; not yet approved by owning capability |
| IDs referenced by the #1728 pilot execution manifest | **4/98**, source references, NOT RUN |
| Remaining #1728 pilot execution-manifest mapping | **94/98 not selected** into four-case pilot; independent of 24 assertion reviews, not proof equivalent tests are absent |
| Confirmed full machine UAT PASS | **0/98 attributed to this catalog checkpoint** |
| Human acceptance | **0/98 attributed to this catalog checkpoint; manual #746 acceptance is recorded separately** |

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
| `UAT-LIF-001` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-LIF-002` | High | Non-UI | [Gherkin](features/lif-data-lifecycle.feature) | First-wave assertions partially audited; no full UAT mapping | NOT RUN / PENDING |
| `UAT-LIF-003` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-LIF-004` | Medium | UI | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
| `UAT-LIF-005` | High | Both | [Gherkin](features/lif-data-lifecycle.feature) | Unverified; capability suite inspection pending | NOT RUN / PENDING |
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

1. Obtain domain-owner review of the 77 newly expanded written procedures against current approved KAORI standards and admitted source routes.
2. Map all 91 Scenario IDs to actually executable pytest/Playwright node IDs and check assertions, roles, fixtures and cleanup; source-only contracts are not browser/provider coverage.
3. Integrate #1725 standards, #1738 catalog, #1726 Playwright and #1727 non-UI test branches into a controlled exact candidate, including synchronizing the stacked #1728 branch with this updated #1738 tree.
4. After the explicit CI/CD hold is lifted, run Developer Check and admission as required, then governed UAT with JUnit, screenshot/trace, committed/provider read-back and a separate human decision.
5. Treat any mandatory SKIP/NOT RUN/FAIL, missing provider authorization, or misleading fake-provider PASS as unresolved. No automatic release readiness is inferred.

