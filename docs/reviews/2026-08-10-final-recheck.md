# KAORI Final Recheck — Release-Candidate Review

## Purpose

This is the canonical page-by-page release review after the KAORI Engineering Standard v1 and layered test strategy were formalized. Previously locked page designs remain baselines; this review fixes only real defects, missing release evidence, stale/legacy ownership, or mismatches with approved shared standards.

Review order:

```text
01 Welcome
02 Kubernetes Dashboard
03 Kubernetes Inventory
04 Kubernetes Governance
05 Kubernetes Operations
06 Kubernetes Analytics
07 Reports
08 Integrations
09 Platform Operations
10 Access
11 Settings
12 Login
```

Intelligence remains outside the current functional/design finalization scope; global quality, architecture, security, and source-hygiene gates still apply.

## Mandatory standard

Every reviewed page uses:

```text
docs/standards/KAORI_ENGINEERING_STANDARD_V1.md
```

A page is not `PASS — LOCKED` until all applicable product, engineering, security, test, documentation, release, and CI/CD evidence is green.

## Global application-shell blocker resolved before page review

Quick Actions, Notification Deck, and Account previously failed together because the navbar embedded one malformed Alpine object program. Canonical ownership is now `app/static/js/navbar.js`, loaded before Alpine and protected by JavaScript syntax/application-shell tests.

## 01 — Welcome

Current verdict: **PASS — LOCKED**

No visual redesign was required. The accepted Welcome composition remains the baseline.

### Findings and dispositions

1. **False permission boundary removed.** `welcome.view` existed in the registry/default roles but never guarded `/` or `/welcome`. Because authenticated session admission is the real product boundary, migration `20260810_retire_welcome_view` removes the residual key and historical role assignments. Downgrade restores the historical default-role assignment only.
2. **Target resolution made independently testable.** First-authorized/universal target policy is now owned by `resolve_welcome_target()`; catalog assembly still owns Flask/current-user presentation behavior.
3. **Test taxonomy expanded.** Unit, Security Regression, Rendering/UI Contract, and End-to-End Smoke are explicit purpose buckets in addition to Functional, Contract, Integration, Migration, and Static Quality.
4. **Stale test-gate references removed.** `verify_feature_test_coverage.py` no longer requires planned Analytics/Inventory test files that do not exist. A domain enters the permanent coverage manifest only when its final-recheck evidence is committed.
5. **Historical styling audit labeled historical.** Current release guidance is the Engineering Standard + Welcome pattern + this record.

### Review matrix

| Review area | Result | Evidence / decision |
|---|---|---|
| Product Contract | PASS | Authenticated role-aware landing catalog; not an infrastructure dashboard. |
| Route/AuthN/RBAC | PASS | `/` and `/welcome` remain `login_required`; synthetic `welcome.view` permission retired. |
| Architecture | PASS | Route → catalog assembly; no provider/repository/runtime infrastructure import. |
| Legacy/dead/compatibility | PASS | Non-enforcing `welcome.view` retired; stale nonexistent test requirements removed. |
| Static Quality | PASS | Authoritative devcontainer toolchain completed successfully. |
| Semantic typography | PASS | Shared Hero/metadata/card typography and Title Case; no technical-value exception needed. |
| Violet/design standard | PASS | Canonical shared Hero, Welcome group, workspace-card, empty-state, shell tokens. |
| Hero | PASS | Right accessory = **Context Icon Box** through canonical `page_hero.context_header(...)`. |
| Tables/status/pagination | N/A | Welcome is a compact workspace catalog. |
| Right content rail | N/A | No content-workspace rail. |
| Tabs | N/A | No peer/local tab navigation. |
| Modal/drawer/inline expand | N/A | No secondary detail disclosure. |
| Toast/loading/notification | PASS / N/A | No Welcome mutation; global shell/Notification Deck follows shared standard. |
| Navbar/sidebar | PASS | Named Alpine controller + shared sidebar; shell regression evidence exists. |
| Light/Dark + responsive | PASS | Shared semantic tokens; stacked/flexible catalog preserves reading order. |
| Accessibility | PASS | One H1, search label, aria-live result count, descriptive cards, visible focus, `/` and Escape behavior. |
| Secure by Design | PASS | Server filters authorized destinations; browser receives no hidden permission/catalog data; no capability network discovery. |
| Performance | PASS | Provider-free landing; bounded in-memory catalog; client search only over rendered cards. |
| Maintainability/readability | PASS | Pure target resolver extracted; release manifest no longer contains fictitious files. |
| Reliability | PASS | No provider dependency; deterministic catalog resolution and global shell timeout/abort contract. |
| Database & migration | PASS | Explicit permission-retirement migration + upgrade/downgrade migration regression. |
| Documentation | PASS | Welcome, RBAC, test taxonomy, quality-gate docs, Engineering Standard, historical audit updated. |
| Static Quality test layer | PASS | Authoritative devcontainer run passed. |
| Contract Test | PASS | `tests/contracts/welcome/test_welcome_navigation_contract.py`. |
| Unit Test | PASS | `tests/unit/welcome/test_welcome_target_resolution.py`. |
| Functional Test | PASS | `tests/welcome/test_welcome_characterization.py`. |
| Integration Test | N/A | Welcome intentionally owns no provider/domain-integration boundary; deterministic E2E covers routing/session/template while infrastructure semantics remain outside the Welcome product contract. |
| Security Regression | PASS | `tests/security/welcome/test_welcome_security.py`. |
| Rendering/UI Contract | PASS | `tests/rendering/welcome/test_welcome_rendering.py`. |
| End-to-End Smoke | PASS | Deterministic Flask/session/application-shell smoke passed in the devcontainer. |
| Release governance | PASS source review | `[Unreleased]`, Semantic Versioning contract, migration and test evidence documented. |
| CI/CD | PASS source review | Same `quality_gate.sh` drives local/CI; deterministic E2E runs explicitly without requiring workstation-local infrastructure. |

### Local audit evidence

The source-only audit environment can run Unit/Security/Rendering/Migration tests but does not contain Flask. These tests pass locally; the E2E smoke and full formatter/type suite remain authoritative in the supported devcontainer/CI environment.

### Lock condition

Welcome is **PASS — LOCKED**. Reopen only for a concrete regression or shared-standard change.

## 02 — Kubernetes Dashboard

Current verdict: **PASS — LOCKED**

No visual redesign was introduced. Final Recheck v3 removed residual compatibility/dead internal surface, corrected snapshot-only wording, formalized the Hero right-side **Context Icon Box** classification, and added permanent L0–L7 release evidence. The final contract/version formatting tails were resolved before the review advanced to Inventory.

The Dashboard remains read-only and provider-free on the web request path; authorization executes before cluster-readiness handling, Cluster Health paginates before snapshot reads, and the reviewed release evidence is now the locked baseline.

## 03 — Kubernetes Inventory

Current verdict: **PASS — LOCKED**

No visual redesign is introduced. The approved Inventory Overview/resource/Topology composition remains the baseline.

### Findings and dispositions

1. **AuthZ-before-readiness fixed.** The clusterless HTMX blocker moved out of Blueprint `before_request` and is now applied inside every protected read path after `inventory.view`, preventing unauthorized requests from probing readiness or receiving an onboarding response before authorization.
2. **Dead surface retired.** Unused `format_byte_count`, `format_gib`, `_split_inventory_values`, and the empty/stale Inventory partial README are removed.
3. **Topology read ownership corrected.** API Server display metadata comes from the eagerly loaded canonical `Cluster.kubernetes_connection` database relationship instead of the Kubernetes integration resolver.
4. **L0–L7 evidence added.** Inventory now has dedicated final-lock, Unit, Functional, Integration, Security, Rendering/UI, E2E, and final Contract evidence.
5. **Canonical documentation updated.** Inventory resource-page pattern v1.2 records committed-generation ownership, AuthZ ordering, Hero Status Badge Box, Full Workspace Modal, resource-header label alignment, SQL pagination, accessibility, and performance/reliability boundaries.
6. **Minor modal alignment defect corrected.** Lifecycle/readiness/collection labels stay below the description but now align with the title/description text column through the shared detail primitive instead of dropping under the leading icon.

### Review matrix

| Review area | Result | Evidence / decision |
| --- | --- | --- |
| Product Contract | PASS source review | Committed Kubernetes asset catalog; no web-time provider fallback. |
| Route/AuthN/RBAC | PASS source review | `inventory.view` precedes clusterless HTMX blocker; sync remains `clusters.sync`. |
| Architecture | PASS source review | Collector/write side separated from committed read models; Topology uses eager-loaded DB relationship. |
| Legacy/dead/compatibility | PASS source review | Orphan helpers/stale placeholder retired; no Blueprint blocker compatibility path retained. |
| Static Quality | PENDING authoritative | Ruff, Ruff Format, djLint, Pyright, Prettier/devcontainer run required. |
| Semantic typography | PASS source review | Human labels Title Case; Kubernetes identifiers retain native casing/technical semantics. |
| Violet/design standard | PASS source review | Shared Hero, tables, labels, modal/drawer, loading and shell components retained. |
| Hero | PASS source review | Resource Hero right accessory = **Status Badge Box**. |
| Tables/status/pagination | PASS source review | Shared table/status components; default 5, options 5/10/25/50. |
| Right content rail | N/A | Resource pages do not own a right-context rail. |
| Tabs | N/A | Resource pages use filters/workspaces; Topology uses visualization controls. |
| Modal/drawer/inline expand | PASS source review | Resource detail = Full Workspace Modal; Overview Side Drawer; Topology adaptive drawer/inspector. |
| Toast/loading/notification | PASS source review | Canonical read loading; sync mutation uses operational feedback; global notification shell unchanged. |
| Navbar/sidebar | PASS inherited shell contract | Shared application shell; Inventory adds no page-local shell state. |
| Light/Dark + responsive | PASS source review | Shared semantic tokens and adaptive workspace/table/detail composition. |
| Accessibility | PASS source review | Shared accessible table/detail/modal/drawer controls and focus behavior. |
| Secure by Design | PASS source review | Unauthorized HTMX cannot probe readiness; read side forbids provider/network clients. |
| Performance | PASS source review | SQL row pagination; current-generation summaries; eager-loaded Topology connection metadata. |
| Maintainability/readability | PASS source review | Residual helpers removed; request/data ownership explicitly documented and verified. |
| Reliability | PASS source review | Reads last committed generation; missing evidence does not trigger provider fallback. |
| Database & migration | N/A for code change | No schema migration required; existing generation model remains canonical. |
| Documentation | PASS source review | Pattern v1.2, domain README, final audit, quality-gate/test docs updated. |
| Contract Test | ADDED / pending authoritative suite | Final release contract plus existing Inventory contracts. |
| Unit Test | ADDED / pending authoritative suite | Topology selection policy. |
| Functional Test | ADDED / pending authoritative suite | AuthZ/readiness request ordering plus existing behavior tests. |
| Integration Test | ADDED / pending authoritative suite | Actual SQLAlchemy node current-generation/pagination read model. |
| Security Regression | PASS source-only targeted | Provider boundary and AuthZ-order contracts. |
| Rendering/UI Contract | PASS source-only targeted | Inventory templates parse and retain canonical shared components. |
| End-to-End Smoke | ADDED / pending devcontainer | Actual Flask/session/layout Inventory smoke with external dependencies isolated. |
| Release governance | PASS source review | `[Unreleased]`; final lock requires full gate before advancing. |
| CI/CD | PASS source wiring / pending run | New verifier/evidence manifest flow through canonical `quality_gate.sh`. |

### Lock condition

Inventory remains design-locked. This targeted modal-alignment fix does not reopen the design; return the verdict to **PASS — LOCKED** after the focused browser/formatter regression passes.

## 04 — Kubernetes Governance

Current verdict: **PASS — LOCKED**

No visual redesign is introduced. The accepted Governance Overview and TLS Certificate Registry remain the baseline.

### Findings and dispositions

1. Blueprint-level clusterless handling is removed so `governance.view`, `tls_certificates.view`, and `tls_certificates.sync` authorize before readiness/blocker behavior.
2. Orphan `get_active_tls_sync_job()` is retired rather than preserved as compatibility surface.
3. Existing TLS data-minimization and mutation-scrubbing boundaries remain unchanged and are promoted into permanent Security Regression evidence.
4. Governance Overview Hero is classified as **Context Icon Box**; TLS Registry Hero uses the canonical **Status Badge Box**. Shared table/status/pagination, Full Workspace Modal, progress toast, Notification Deck and Activity Audit remain unchanged.
5. Governance now owns permanent L0–L7 release evidence and a final-lock verifier in the canonical quality gate.
6. TLS wildcard matching is corrected to single-label semantics, preventing `*.example.com` from being interpreted as covering deeper multi-label hostnames.
7. Governance standalone certificate-policy tests now restore temporary `sys.modules` packages, making collection order deterministic and preventing the fake-package `create_app` import failure.

### Lock condition

Governance becomes **PASS — LOCKED** only after authoritative Static Quality, Contract, Unit, Functional, Integration, Security, Rendering/UI, E2E, browser smoke, and full release gate pass.

## 05 — Kubernetes Operations

Current verdict: **TARGETED FIX — AUTHORITATIVE VALIDATION PENDING**

The final recheck intentionally reopens presentation composition because retiring the former content right rail left ConfigMap and Secret CRUD workspaces stretched across the available width. Browser review rejected both blanket full-width and custom task-rail experiments. `Create Kubernetes ConfigMap` established the approved **Form + Right Context** reference derived from the existing Kubernetes, Prometheus, and Alertmanager registration forms. The same shared geometry is now applied to ConfigMap Update/Delete, Secret Create/Replace/Delete, and the Protected Reveal `New Request` task.

### Findings and dispositions

1. **AuthZ-before-readiness fixed.** The Kubernetes Operations Blueprint clusterless `before_request` is retired. `cluster_required()` executes only inside route RBAC for ConfigMap, Secret CRUD, Protected Reveal, and TLS operations.
2. **Form + Right Context propagated.** ConfigMap Create/Update/Delete and Secret Create/Replace/Delete now consume `form_with_context_rail.html`; workflow and safety guidance live in canonical right-side boxes while validation and mutation actions remain in the main task.
3. **Protected Reveal split by task type.** The `New Request` tab uses Form + Right Context for target/request controls and security guidance, while `My Requests` and `Approvals` remain full-width registries. TLS workflows retain their dedicated reviewed compositions.
4. **Shared ownership increased.** `form_with_context_rail.html` owns the 8/12 + 4/12 geometry; `info_flow.html` and `information_guide_card.html` own side guidance. `kubernetes_operation_ui.html` remains the owner for reusable special workflow and action primitives.
5. **L0–L7 evidence added.** Operations now has dedicated Contract, Unit, Functional, Integration, Security, Rendering/UI, E2E, and final-lock evidence.
6. **Documentation ownership formalized.** Form + Right Context is now an approved reusable design option with shared geometry, canonical side-box ownership, and a future behavior-neutral DRY migration path for Integration registration pages.
7. **Protected Reveal navigation and lifecycle corrected.** Peer views now use Integrated Workspace Tabs instead of Compact Segmented Tabs; URL/deep-link state activates the correct panel, request submission returns to `My Requests`, approval decisions stay in `Approvals`, and step-up is presented only after a request is approved.
8. **Protected Reveal refresh stability hardened.** Initial panel ownership remains server-authoritative until the client validates a complete tab/panel pair; explicit `reveal_view` state wins over stale hashes while valid hash-only deep links require a complete tab/panel pair, and the Platform Operations cross-lock now follows the current Form + Right Context ownership.

### Lock condition

Operations becomes **PASS — LOCKED** only after authoritative Static Quality, all L0–L7 evidence, browser regression across ConfigMap/Secret workflows, and the full release gate pass.

## 06 — Kubernetes Analytics

Current verdict: **TARGETED FIX — AUTHORITATIVE VALIDATION PENDING**

Final recheck covers Overview, Utilization, Capacity, Storage, Workload, Forecast, Top Consumers, and Alerts & Anomalies. Review proceeded by explicit user direction while the remaining Kubernetes Operations release-gate confirmation is still pending. Analytics removes dual tab ownership, stops internal snapshot identifiers leaking into Overview navigation, formalizes shared Content Tabs, retires dead compatibility surfaces, makes materialized decode ORM-free, and adds permanent L0–L7 release evidence.

### Lock condition

Analytics becomes **PASS — LOCKED** only after authoritative Static Quality, Contract, Unit, Functional, Integration, Security, Rendering/UI, E2E, browser regression, and the full release gate pass.

## Next review

`07 — Reports` is next only after the outstanding Kubernetes Operations confirmation and Kubernetes Analytics final gate are both green.

### CRUD Form Alignment and Secret Replace Action Follow-Up

- ConfigMap and Secret CRUD target rows now use the shared `components/form_field.html` vertical-alignment contract: equal label-row height, `h-10` controls, and helper text below controls.
- Protected Secret Reveal target selectors use the same field baseline.
- Secret Replace renders Validate/Replace actions inside the HTMX-refreshed content partial so selecting a target cannot leave the page without its mutation controls.
- The Design System and Design README again register `docs/standards/KAORI_ENGINEERING_STANDARD_V1.md` as the mandatory final-recheck engineering index.
