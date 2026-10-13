# KAORI UAT Gherkin Scenario Specifications

> **Scope:** #1738 retrospective acceptance backlog, under foundation #1724. Normative scenario/acceptance records: #1725 and `docs/TESTING.md`. This folder is a readable **specification**, not a replacement test runner or source of UAT PASS.

## How to read and comment

Read one `.feature` file per KAORI capability, click the scenario with its stable `UAT-<CAPABILITY>-NNN` ID, and review the standard **Given (preconditions) → When (action) → Then (expected result)** sequence. `And` extends the preceding step. A `Background` lists shared context, not a test execution. `@negative`/`@positive`, `@ui`/`@non_ui`, `@high`/`@medium`, `@detailed`/`@draft` indicate classification and detail maturity. **Execution outcome is not encoded in Gherkin tags** because a scenario is reusable across candidates.

**Feedback:** add a comment on [#1738](https://github.com/OXY7O/KAORI/issues/1738), citing the exact ID and the Given/When/Then line that should change. Mention the feature and role, expected committed state, provider/audit read-back, negative/security path or UI geometry, as applicable. Never include secrets. Gherkin text is written in English for consistency with KAORI's approved technical documentation; discuss refinements in Indonesian if you prefer.

## Execution and ownership boundaries

- **91 scenarios in 18 capability files**, exactly matching the [scenario catalog](../KAORI_UAT_SCENARIO_CATALOG.md). **14 `@detailed` scenarios** expand the existing [first-wave procedures](../KAORI_UAT_FIRST_WAVE_CASES.md); **77 `@draft` scenarios** use catalog-level actions and expected results and need owner refinement before becoming full executable cases.
- Existing pytest/Playwright nodes, domain fixtures, JUnit, screenshot/trace and provider/audit evidence are implementation/execution owners. See the [test mapping audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md); a Gherkin `@UAT-...` tag does not execute a test or create a pytest marker.
- **Execution status belongs to candidate-bound evidence, never the reusable `.feature` files.** At the initial authoring checkpoint (2026-10-13), none of the 91 scenario IDs had a specific UAT execution result and human acceptance remained PENDING. For current results consult the owning Issue/PR execution records. Unrelated historic CI PASS is not scenario acceptance.
- Provider mutation is only allowed in a governed disposable sandbox with read-back/cleanup and explicit permission. Simulated/fake-provider test results do not prove real-provider UAT.
- Acceptance requires exact source SHA/tree, deployed digest if relevant, actual runner/timestamp and result, meaningful assertions and evidence, findings/retest, and a separate authorized human decision. No PR, CI/CD, or new Gherkin/Cucumber runtime is introduced by these files.

## Feature index

| Capability | Scenarios | Positive | Negative | Expanded details | Gherkin source |
| --- | ---: | ---: | ---: | ---: | --- |
| Authentication & Sessions | 5 | 2 | 3 | 1 | [`aut-authentication-sessions.feature`](features/aut-authentication-sessions.feature) |
| Access — Users, Roles, Permissions & Identity Providers | 6 | 2 | 4 | 1 | [`iam-access-rbac.feature`](features/iam-access-rbac.feature) |
| Kubernetes — Cluster Registration & Provider Readiness | 4 | 1 | 3 | 0 | [`kcl-kubernetes-clusters.feature`](features/kcl-kubernetes-clusters.feature) |
| Kubernetes — Dashboard, Inventory & Topology | 5 | 2 | 3 | 0 | [`inv-kubernetes-inventory.feature`](features/inv-kubernetes-inventory.feature) |
| Kubernetes — Analytics & Forecast | 4 | 2 | 2 | 0 | [`kan-kubernetes-analytics.feature`](features/kan-kubernetes-analytics.feature) |
| Kubernetes — Governance & TLS | 4 | 2 | 2 | 0 | [`gov-kubernetes-governance.feature`](features/gov-kubernetes-governance.feature) |
| Kubernetes — Tenant Management | 8 | 3 | 5 | 3 | [`ten-kubernetes-tenant.feature`](features/ten-kubernetes-tenant.feature) |
| Kubernetes — ConfigMaps, Secrets & Resource Operations | 5 | 2 | 3 | 1 | [`kop-kubernetes-operations.feature`](features/kop-kubernetes-operations.feature) |
| Object Storage — Inventory & Analytics | 4 | 2 | 2 | 0 | [`ost-object-storage.feature`](features/ost-object-storage.feature) |
| Artifact Registry — Inventory, Security, Runtime & Governance | 5 | 2 | 3 | 1 | [`reg-artifact-registry.feature`](features/reg-artifact-registry.feature) |
| Integrations — Registry, Provider Configuration & Runtime | 5 | 2 | 3 | 1 | [`ing-integrations.feature`](features/ing-integrations.feature) |
| Notification Channels & Activity Center | 4 | 2 | 2 | 0 | [`ntf-notifications.feature`](features/ntf-notifications.feature) |
| Intelligence — Recommendations, Alerts, Catalog & Automation Control | 5 | 2 | 3 | 0 | [`inl-intelligence.feature`](features/inl-intelligence.feature) |
| Reports — Generate, Generated, Templates, Schedules & Storage | 7 | 3 | 4 | 2 | [`rpt-reports.feature`](features/rpt-reports.feature) |
| Platform Operations — Overview, Jobs & Executions | 4 | 2 | 2 | 0 | [`ops-platform-operations.feature`](features/ops-platform-operations.feature) |
| Platform Operations — Data Lifecycle & Secret Reveal | 5 | 2 | 3 | 1 | [`lif-data-lifecycle.feature`](features/lif-data-lifecycle.feature) |
| Shared Shell, Settings, Visual QA & Accessibility | 7 | 3 | 4 | 2 | [`uix-shared-ui-ux.feature`](features/uix-shared-ui-ux.feature) |
| Release & Server UAT Operational Evidence | 4 | 2 | 2 | 1 | [`rel-release-uat.feature`](features/rel-release-uat.feature) |
| **Total** | **91** | **38** | **53** | **14** | |

## Example: how a Gherkin spec maps to executable evidence

```text
UAT-TEN-002 [negative, UI + non-UI]
  -> Given/When/Then acceptance statement (.feature)
  -> Existing Playwright browser interactions + domain pytest negative assertions
  -> Exact-candidate JUnit + screenshot/trace + committed DB + provider/audit read-back
  -> Machine outcome: PASS / FAIL / BLOCKED / NOT RUN / approved N/A
  -> Named human reviewer independently ACCEPTS / REJECTS / leaves PENDING
```

The full scenario steps and expected results live in the `.feature` files; test automation should never be duplicated in a second Gherkin step-definition framework without separately approved architecture authority.
