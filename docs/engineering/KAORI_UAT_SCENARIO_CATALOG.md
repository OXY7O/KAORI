# Retrospective KAORI Acceptance Scenario Catalog — Baseline v0.1

**Authority:** #1738 under #1724; specification/record format under #1725 (`docs/TESTING.md`), current source-first engineering & delivery standards. This is a **non-normative planning catalog** to backfill missing execution coverage. It is *not* a new testing framework, a visual standard, a release gate, or a claim of test PASS.

**Observed source snapshot:** `kaori/review/staging-uat@0415d1832adcdb7bd30bd3f2d32e4940c90335af`, 2026-10-13 (source inspection only). **Work branch base:** `kaori/staging@79bbb7466c60b9781358c3e26faf476ab0c54bf1`. The reviewed candidate may include features not yet integrated into staging; revalidate all scenario implementation availability and exact code/test paths on the eventual admitted staging SHA. **Do not modify** #1710's frozen admission candidate.

## Complete 150 written acceptance test cases

[Review all 150 detailed acceptance cases](KAORI_UAT_ALL_CASES.md): per-case preconditions, steps, expected results, evidence and cleanup. The 14 first-wave cases retain their original procedures; 136 were expanded and require domain-owner verification before executable mapping. This is **specification completeness, not runtime PASS or gate readiness**.

## Read the scenarios as Gherkin code

**[Open the Gherkin Feature Index](uat/README.md)** to browse **21 `.feature` files containing all 150 Scenario IDs**. Each feature contains `Given / When / Then` expectations; the 14 first-wave cases have expanded steps and the other 136 are tagged `@owner_review`. Comment on #1738 with the stable `UAT-...` identifier and the particular step or missing positive/negative path. These files are human-readable specifications, **not an additional test runner or UAT PASS evidence**.

**2026-10-24 scope refinement:** Added Welcome-owned scenarios from #746 and one read-only Access authorization scenario without reusing IAM mutation coverage. Scenario ID/count changes are new specifications only; historic #1738 original 91-case mapping is not retroactively executed. No hard-coded expected 16/13 count in reusable tests; derive role counts from current effective permissions.

**2026-10-24 Kubernetes Admin addendum:** Existing `UAT-LIF-004` was reconciled to the canonical integrated Overview/Secret Reveal page and inline editor. `UAT-LIF-006`–`013` cover search, filters and pagination; unsaved Cancel; approved Harbor policy save/rollback with Activity Audit; Viewer read denial; unexecuted POST/CSRF negatives; unavailable source/cluster; Warning-vs-Error detail; and keyboard/responsive light-dark coverage. **Human Accepted** Batch 01–06 results belong to owning issue #2605 and #2457, not to machine-attributed execution of newly authored Gherkin IDs. No claim that all negative/visual matrix cases ran.

**Object Storage Dashboard addendum (#3168):** UAT-OSD-001–010 describe dashboard acceptance, distinct from UAT-OST-001–004 Inventory/Analytics. Operator visually reviewed tabs and supplied focused green pytest/lint evidence, but no exact-ID Gherkin execution, report download, provider failure, RBAC, responsive/dark or multi-system negative results.

**Object Storage Inventory acceptance (2026-10-25; #3186):** The operator explicitly accepted the bounded Dev Container Inventory Overview, Systems and Buckets & Containers UAT, including filtered `kaori` and the native detail header/evidence rails. Last reported checks: djlint PASS, Ruff check PASS, Ruff format PASS, **15 focused pytest PASS in 1.61s**. The user's exact local HEAD was not supplied; remote holding branch `1b0f75f1` was verified separately. These results do **not** establish execution of individual `UAT-OST-001`–`011`. Provider outage, RBAC denial, real multi-system fixture and full light/dark/narrow testing remain NOT RUN. Official CI/CD HOLD.

## Reviewer guide — where to inspect and comment

All scenarios are visible in this document on the **work branch**, before any PR or CI/CD action. Use your browser's Find (Ctrl/Cmd+F) with a stable ID such as `UAT-TEN-004` to inspect the scenario row and the owning capability. This inventory is not yet complete for every dynamic route/state and all entries are **NOT RUN** against an accepted UAT candidate.

1. **Browse all capability scenarios:** this [catalog](KAORI_UAT_SCENARIO_CATALOG.md) lists positive/negative cases, intended UI/non-UI checks and expected outcomes.
2. **Read detailed steps and evidence:** [first-wave UAT procedures](KAORI_UAT_FIRST_WAVE_CASES.md) expand the 14 initial higher-risk scenarios into preconditions, actions, assertions, and isolation/cleanup.
3. **Compare existing tests and uncovered gaps:** [source-level mapping audit](KAORI_UAT_TEST_MAPPING_AUDIT.md) differentiates partial test assertions, source-only contracts and unproven end-to-end paths.
4. **Submit feedback in [issue #1738](https://github.com/OXY7O/KAORI/issues/1738)** rather than editing the normative testing standard. Include Scenario ID (or request a new ID), the affected capability/screen, scenario type, exact steps (especially buttons/inputs/roles), expected behavior, and impact. Attach a sanitized screenshot or link if relevant; never post credentials or sensitive provider data.

**Example feedback:** `UAT-UIX-002 — Negative / Reports Generate dialog — at 360×800, invalid input must show an accessible field error while Save and Cancel remain reachable without horizontal scrolling. Add post-validation screenshot and keyboard focus assertions.`

Existing test assertions are source-reviewed, not necessarily executed. New work branches under #1726 (UI) and #1727 (non-UI) implement gaps independently; a committed test still stays **NOT RUN** until the runner produces exact-candidate evidence and an authorized human reviews it.

## Method and execution truth

This catalog supplements the approved standards and is scoped to **currently discovered** capabilities (not a guarantee that every endpoint/action has been inventoried). Canonical product direction is `docs/product/README.md`. Navigation uses `app/common/navigation.py`; capability ownership uses domain READMEs and paths. Browser coverage must reuse #222/#543 Playwright and `tests/ui/visual_audit.py`, whose current deterministic visual surface set is limited to Welcome, Settings General and Notification Center. Many parameterized/provider-dependent or dynamically composed UI states are **not yet proven by that deterministic set**.

Every listed scenario is a **specified candidate, not executed**:

- **Specification:** yes (this catalog; some first-wave cases expanded in the companion execution specification).
- **Automation assertion mapping:** **UNVERIFIED**; the existing test folders below are *candidate owners only*, not proof that an individual scenario is implemented, reaches a real browser, or has passed.
- **Execution outcome against target candidate:** **NOT RUN per Gherkin ID** for machine-attributed scenario execution; scoped human Kubernetes Admin UAT was explicitly accepted separately on #2605. Historical CI/tests may have other valid results; they are not silently re-attributed to these IDs.
- **Human acceptance:** **PENDING per newly mapped Scenario ID** unless exact attribution is subsequently reviewed; human acceptance of the bounded Kubernetes Admin workflow is recorded on #2605. No synthetic data or AI assessment grants sign-off.
- **Safety:** simulated provider evidence is not real-provider UAT; provider mutations require controlled sandbox, explicit permission, isolation/cleanup, and read-back. Inactive, unsupported, or still-governance-only functions must be tested as correctly unavailable, *not* treated as required successful mutations.

### Risk and wave selection

Reuse existing GitHub Priority words *High / Medium / Low* as risk descriptions, **not** as new GitHub metadata fields. Select first-wave execution by adverse impact: access escalation, irreversible provider/data mutation, false success, loss of committed evidence, wrong cross-provider identity, unsafe release, then routine navigation, UX and analytics. Risk classification must be reviewed per capability before execution.

- **Wave 1 — critical boundaries:** Authentication/RBAC; Tenant adoption/allocation; ConfigMap/Secret/TLS; Integration/provider source isolation; Artifact Registry vulnerability/runtime truth; Reports worker/scope/storage; Data Lifecycle/Secret Reveal; deployment SHA/digest; mandatory UI interaction and clipping checks.
- **Wave 2 — operational correctness:** Kubernetes/Object Storage/Analytics state freshness, Intelligence & Jobs correlation, scheduling, advanced negative/retry/recovery, cross-domain navigation.
- **Wave 3 — broad UX:** all scoped authenticated routes, extra parameters/states, light/dark/viewport snapshots and exploratory human visual acceptance.

A selected scenario needs actual Given/When/Then plus UI/DB/provider/audit assertions and meaningful JUnit/Playwright evidence; **the listing below alone never changes an acceptance result**. For pre-existing UI, test at least the page state before and after meaningful clicks/input/submit/filter, not just initial render.

## Capability-first scenario inventory

Each row reads as an abbreviated **Given precondition → When action → Then expected outcome**. Expand into full steps before execution; dynamic route/actions must be confirmed on the admitted candidate. `Both` means UI behavior plus non-UI state/security/provider assertions, not one screenshot counted twice.


### Authentication & Sessions (`UAT-AUT-*`)

**Owning source:** app/access/authentication/. **Candidate test owner(s), not verified mapping:** tests/access/authentication/; tests/security/access/; tests/ui/. **Shared preconditions:** Local test user, session fixtures and configured auth method; never expose real credentials.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-AUT-001` | Positive | Both | High | Valid active user logs in | Authenticated session, authorized navigation and correct audit/feedback are produced |
| `UAT-AUT-002` | Negative | Both | High | Invalid password or disabled account attempts login | Access denied, no admitted session, no misleading success or secret disclosure |
| `UAT-AUT-003` | Negative | Non-UI | High | Expired/revoked session submits a protected request | Server rejects request regardless of previously rendered UI |
| `UAT-AUT-004` | Negative | Both | High | CSRF token is missing/invalid on a protected mutation | Mutation rejected with no committed/provider side effects |
| `UAT-AUT-005` | Positive | UI | Medium | User signs out and uses Back or bookmarked authenticated URL | Session ended, protected content cannot be recovered without login |

### Access — Users, Roles, Permissions & Identity Providers (`UAT-IAM-*`)

**Owning source:** app/access/README.md; app/access/rbac/; app/access/identity_providers/. **Candidate test owner(s), not verified mapping:** tests/contracts/access/; tests/access/users/; tests/security/access/; tests/ui/. **Shared preconditions:** Operator and restricted-user identities, known roles/permissions, isolated Identity Provider fixture.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-IAM-001` | Positive | Both | High | Permitted admin creates/updates user and role assignment | Persisted identity/role state, correct directory UI, safe Activity evidence |
| `UAT-IAM-002` | Negative | Both | High | Restricted user opens hidden or direct role/user mutation URL | Server denies mutation; hiding navigation alone is not authorization |
| `UAT-IAM-003` | Negative | Non-UI | High | Protected role or forbidden permission escalation is submitted | Canonical RBAC guard rejects; no effective privilege expansion |
| `UAT-IAM-004` | Positive | UI | Medium | Admin filters User Directory/Permission Catalog and clears filters | Canonical default five rows, page one reset, selected row count preserved |
| `UAT-IAM-005` | Negative | Both | High | Identity Provider is disabled, invalid or unreachable during auth | No fallback that admits an unauthorized identity; error state identifies dependency |
| `UAT-IAM-006` | Negative | UI | Medium | Role/user modal or validation form receives missing and malformed fields | Actionable inline error; no partial entity creation; focus retained |
| `UAT-IAM-007` | Negative | Both | High | Viewer directly requests Access Overview using GET /access/ | Server returns 403 with actionable Access Denied guidance, protected data absent |

### Kubernetes — Cluster Registration & Provider Readiness (`UAT-KCL-*`)

**Owning source:** app/kubernetes/cluster/; app/integrations/orchestration/. **Candidate test owner(s), not verified mapping:** tests/contracts/kubernetes/; tests/kubernetes/; tests/integrations/. **Shared preconditions:** Disposable/sandbox Kubernetes API or mock for CI; read-only real-provider UAT when approved.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-KCL-001` | Positive | Both | High | Permitted operator registers a valid cluster and validates connection | Correct cluster identity/readiness, committed configuration and audit evidence |
| `UAT-KCL-002` | Negative | Both | High | Cluster credentials/endpoint/TLS trust are invalid | Clear validation failure; no false Connected/Ready state or leaked credential |
| `UAT-KCL-003` | Negative | Non-UI | High | Provider is unavailable after committed cluster inventory exists | Read-only committed state remains truthful; live writes fail closed |
| `UAT-KCL-004` | Negative | Both | High | Restricted user submits cluster configuration mutation | Authorization denial and no external or committed mutation |

### Kubernetes — Operations Dashboard (`UAT-KDB-*`)

**Owning source:** `app/kubernetes/dashboard/`; shared `components/operational_dashboard_workspace.html`, `operational_recommendation_cards.html` and `reporting_dashboard_workspace.html`. **Sources of authority:** #937, #753, #758; operator Human UAT Acceptance on 2026-10-24. **Candidate test owners:** `tests/kubernetes/dashboard/`, `tests/e2e/kubernetes/dashboard/`, `tests/contracts/dashboards/`, `tests/unit/kubernetes/dashboard/`, `tests/ui/`. **Evidence boundary:** completed manual dashboard human acceptance is in #937; individual reusable Scenario IDs below are NOT RUN until a candidate-specific execution mapping exists.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-KDB-001` | Positive | UI | High | Open the dashboard and inspect Hero, scope, source freshness and all eight KPI cards | Hero and KPI identity match the selected cluster with explicit committed source; initial shell avoids live provider calls |
| `UAT-KDB-002` | Positive | Both | High | Open Operations Overview; compare connectivity KPI with Cluster Health composite severity and health table | Connected/Healthy registration does not hide composite Critical or alert reason; cluster scoped health table defaults to five rows |
| `UAT-KDB-003` | Positive | Both | Medium | Select Capacity & Demand; verify Data Scope, CPU/Memory/Pods, chart history/projection and source-derived conclusion | Exclude control-plane capacity; show actual worker headroom, projected percentage/horizon, guarded actions and no fabricated series |
| `UAT-KDB-004` | Positive | UI | High | Select Signals & Actions; compare KPI vs Alerts Summary, review top-five preview and six governance steps | Totals consistent with all selected-scope cases; latest preview at most five; Critical not suppressed; shared response steps/source present |
| `UAT-KDB-005` | Positive | UI | Medium | Inspect P1/P2 badges and title/description; hover title, activate authorized Intelligence detail link | Shared renderer shows at most five cards with 2-line title and 2-line description, intact source footer and accessible full detail |
| `UAT-KDB-006` | Positive | Both | High | Open Reporting, verify recent activity, select Open Reports Workspace, locate the Ready Analytics Overview Report and download | Correct scoped report and lifecycle record; at most four recent reports; successful actual download of chosen artifact without claiming all artifacts available |
| `UAT-KDB-007` | Positive | UI | Medium | Navigate all four tabs, refresh, Back/Forward; inspect full page/card/table/chart and visual baseline at each viewport/theme | One visually active tab, correct panel and URL state, no clipped actions or horizontal overflow, no unreviewed baseline acceptance |
| `UAT-KDB-008` | Negative | Both | High | Open dependent Dashboard sections and inspect empty/partial/error states, readiness, source and absence of provider queries | Not Collected/Unavailable/Partial replaces false zero or Healthy claims; unrelated committed inventory remains visible; no external mutation |
| `UAT-KDB-009` | Negative | Both | High | Switch scope A to B/All; request lazy capacity, alerts and reporting with stale or foreign scope ID | No foreign metrics, AlertCases, reports or detail rows; selected scope prerequisite honored; all-cluster reports Kubernetes-only |
| `UAT-KDB-010` | Negative | Both | High | Request /dashboards/kubernetes/ and lazy section endpoints directly; inspect HTTP, rendered denial and absence of work | No unauthorized content; authz runs before section builders/read, no job or provider mutation or leakage |

### Kubernetes — Dashboard, Inventory & Topology (`UAT-INV-*`)

**Owning source:** app/kubernetes/dashboard/; app/kubernetes/inventory/. **Candidate test owner(s), not verified mapping:** tests/kubernetes/dashboard/; tests/kubernetes/inventory/; tests/contracts/kubernetes/; tests/ui/. **Shared preconditions:** Selected-cluster committed snapshots including empty, stale, multiple clusters and representative objects.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-INV-001` | Positive | UI | Medium | Operator opens Cluster/Dashboard then Inventory lists and details | Correct selected-cluster scope, navigation, row/detail identity and shared table UI |
| `UAT-INV-002` | Negative | Both | High | Inventory evidence is stale, missing or partially collected | UI explicitly displays stale/partial/unknown, not fabricated Healthy/zero |
| `UAT-INV-003` | Negative | Non-UI | High | Same-name object is recreated with a different provider UID | Old/new identities are not conflated; lineage and correlation remain correct |
| `UAT-INV-004` | Positive | UI | Medium | Filter/sort/page Inventory records including zero-result state | Filters persist across HTMX navigation; pagination and No Results follow shared standard |
| `UAT-INV-005` | Negative | Both | High | Topology relationship source is absent or inconsistent | No invented dependency edges or misleading cross-cluster relationship |

### Kubernetes — Analytics & Forecast (`UAT-KAN-*`)

**Owning source:** app/kubernetes/analytics/; app/analytics/. **Candidate test owner(s), not verified mapping:** tests/kubernetes/analytics/; tests/contracts/analytics/; tests/ui/. **Shared preconditions:** Committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-KAN-001` | Positive | Both | Medium | Operator selects cluster/time range and opens utilization/capacity/forecast | Charts and summaries retain chosen scope, units, time window and source freshness |
| `UAT-KAN-002` | Negative | Both | High | Metrics source becomes unavailable or returns no data | Never display zero as measured utilization or unknown as Normal |
| `UAT-KAN-003` | Negative | Non-UI | High | Invalid/out-of-scope metrics binding or scope is submitted | No cross-cluster fallback or fabricated demand/capacity forecast |
| `UAT-KAN-004` | Positive | UI | Medium | Charts, selectors and tables render under light/dark and narrow viewports | Labels/legends visible, no horizontal document overflow or clipped actions |

### Kubernetes — Governance & TLS (`UAT-GOV-*`)

**Owning source:** app/kubernetes/governance/; app/kubernetes/operations/. **Candidate test owner(s), not verified mapping:** tests/kubernetes/governance/; tests/kubernetes/operations/; tests/security/kubernetes/. **Shared preconditions:** Safe namespace/TLS fixtures and governance snapshots; real mutation only in approved sandbox.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-GOV-001` | Positive | Both | High | Operator reviews TLS certificate inventory and governance finding | Certificate identity, expiry/source and readiness reflect authoritative evidence |
| `UAT-GOV-002` | Negative | Both | High | TLS rotation preflight fails (identity/permission/impact) | Change is blocked; original Secret/cert remains unchanged |
| `UAT-GOV-003` | Negative | Non-UI | High | Capacity/quota or policy evidence is expired or conflicting | Mutation admission fails closed; no optimistic capacity claims |
| `UAT-GOV-004` | Positive | UI | Medium | Operator moves from governance finding to source evidence | Scoped navigation, accessible details and consistent blocked/error states |

### Kubernetes — Tenant Management (`UAT-TEN-*`)

**Owning source:** app/kubernetes/tenant/README.md; #125. **Candidate test owner(s), not verified mapping:** tests/kubernetes/tenant/; tests/contracts/kubernetes/; tests/ui/. **Shared preconditions:** Native test cluster with disposable Namespace, verified UID/resourceVersion, permitted and restricted identities.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-TEN-001` | Positive | Both | High | Permitted operator discovers, preflights and adopts existing Native Namespace | One adopted generation and correct provider/audit identity; no unauthorized mutation |
| `UAT-TEN-002` | Negative | Both | High | Namespace UID/resourceVersion changes after preflight before submit | Reject stale adoption, no partial records/provider changes or false success |
| `UAT-TEN-003` | Positive | Both | High | Create Tenant/Namespace from approved Resource Profile within budget | Committed pinned profile version, allocation and provider read-back match |
| `UAT-TEN-004` | Negative | Both | High | Allocation change exceeds governed headroom or mismatches pinned version | Preview blocks submit and preserves preexisting effective quotas |
| `UAT-TEN-005` | Negative | Both | High | Restricted or self-approving actor attempts credential/Access Grant escalation | Server denies or requires independent approval; secrets are not exposed |
| `UAT-TEN-006` | Negative | Both | High | Provider patch succeeds but KAORI commit/read-back fails | No false complete state; recovery evidence identifies possible provider residue |
| `UAT-TEN-007` | Positive | UI | Medium | Resource Profile/Create/Allocation modal is opened and completed | Shared modal/input/validation, labels, toast and frozen allocation version rendered correctly |
| `UAT-TEN-008` | Negative | Both | High | Tenant released/re-adopted identity is reused or foreign Capsule owner appears | Fail closed against wrong generation/foreign owner; never silently take over |

### Kubernetes — ConfigMaps, Secrets & Resource Operations (`UAT-KOP-*`)

**Owning source:** app/kubernetes/operations/; app/platform_operations/kubernetes/. **Candidate test owner(s), not verified mapping:** tests/kubernetes/operations/; tests/platform_operations/test_secret_reveal_htmx_save.py; tests/security/kubernetes/. **Shared preconditions:** Dedicated disposable namespace and test Secret/ConfigMap; guarded reveal/rotation policy.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-KOP-001` | Positive | Both | High | Permitted operator creates/edits ConfigMap in sandbox | Provider read-back matches intended data; KAORI job/activity evidence accurate |
| `UAT-KOP-002` | Negative | Both | High | ConfigMap submit/delete uses stale identity, missing rights or conflict | No unintended overwrite/delete; operator gets actionable feedback |
| `UAT-KOP-003` | Positive | UI | Medium | Secret operation form loads and validates bounded metadata | Form labels, modal, loading, focus, feedback and layout follow shared standards |
| `UAT-KOP-004` | Negative | Both | High | User without reveal policy requests Secret material | No Secret value disclosure via UI, response, logs, trace or audit |
| `UAT-KOP-005` | Negative | Non-UI | High | TLS Secret rotation encounters wrong target or partial provider failure | No false rotation success; pre/post identity and recovery evidence preserved |
| `UAT-KOP-006` | Positive | Both | High | Authorized single TLS Secret rotation after valid pair and complete SAN coverage | Only selected TLS Secret changes; stable UID, advanced resourceVersion and matching provider fingerprint |
| `UAT-KOP-007` | Negative | Both | High | Single TLS rotation validates a mismatched key or uncovered Ingress SAN | Validation fails closed; Update disabled and original Secret remains unchanged |
| `UAT-KOP-008` | Positive | Both | High | Authorized bulk TLS rotation of two selected committed Secrets with modal confirmation | Two targets validated then explicitly confirmed; per-target provider read-back, audit and truthful outcomes |
| `UAT-KOP-009` | Negative | UI | Medium | Bulk native modal dismiss/invalidation and responsive safe presentation | No PATCH on dismissal, focus restored and file/target change requires revalidation |

### Object Storage — Operations Dashboard (`UAT-OSD-*`)

**Owning source:** app/storage/object_storage/dashboard/. **Candidate test owners, not individually mapped:** tests/contracts/storage/object_storage/dashboard/; tests/contracts/dashboards/. **Human evidence:** 2026-10-25 visual review of four tabs with MinIO X300 and All Systems, distinct from scenario-ID machine evidence.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-OSD-001` | Positive | UI | High | Dashboard shell and four KPIs use committed scope | the Violet Hero displays selected scope and Committed Snapshots authority |
| `UAT-OSD-002` | Negative | Both | High | Stale analytics does not conceal warning posture | the health table displays Warning for stale analytics |
| `UAT-OSD-003` | Positive | Both | Medium | All Systems and selected-scope switching stays correlated | All Systems shows Systems Buckets Inventory Usage and Analytics Ready |
| `UAT-OSD-004` | Positive | Both | Medium | Capacity forecast and Top Consumers use committed measurements | capacity balance and projections use committed source measurements |
| `UAT-OSD-005` | Positive | UI | High | Signals retain AlertCase severity and governed response | severity and up to five previews derive from KAORI AlertCase records |
| `UAT-OSD-006` | Positive | UI | Medium | Recommendations use shared bounded previews and Intelligence detail | title and description previews use two-line clamp like Kubernetes |
| `UAT-OSD-007` | Positive | Both | High | Reporting empty state is distinct from a Ready report download | zero report counts show actionable no-report empty state |
| `UAT-OSD-008` | Positive | UI | Medium | Four tabs retain URL theme and responsive behavior | only one active tab and matching lazy section is visible |
| `UAT-OSD-009` | Negative | Both | High | Missing or invalid Object Storage scope cannot fake metrics | missing measurements show unavailable rather than zero or Healthy |
| `UAT-OSD-010` | Negative | Both | High | Restricted direct Dashboard and section requests are denied | authorization denies protected content before expensive reads |

### Object Storage — Inventory & Analytics (`UAT-OST-*`)

**Owning source:** app/storage/object_storage/; app/integrations/storage/object_storage/. **Candidate test owner(s), not verified mapping:** tests/storage/object_storage/; tests/contracts/storage/; tests/integrations/. **Shared preconditions:** Isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-OST-001` | Positive | Both | Medium | Operator views registered Object Storage systems and bucket inventory | Correct system identity, bucket scope, committed metrics and details |
| `UAT-OST-002` | Negative | Both | High | Object Storage provider is unreachable, disabled or returns partial results | Truthful unknown/stale/degraded presentation; no fabricated empty bucket list |
| `UAT-OST-003` | Positive | UI | Medium | Bucket registry search/filter/pagination and details interaction | Five-row default, stable filters, accessible detail/modal and clear feedback |
| `UAT-OST-004` | Negative | Non-UI | High | Forecast/usage receives mismatched source or missing data | No cross-system substitution, bogus zero capacity or unsupported trend claim |
| `UAT-OST-005` | Positive | UI | Medium | Inventory Overview separates collection readiness from protection attention | the Hero and Inventory Data Snapshot show registered system and committed 1-of-1 coverage |
| `UAT-OST-006` | Positive | UI | Medium | Systems table preserves provider identity, filters and committed freshness | the system appears exactly once with provider, environment, release, endpoint and snapshot status |
| `UAT-OST-007` | Positive | UI | Medium | System detail displays provider connection and snapshot evidence without mutation | the detail identifies the system, provider connection, compatibility profile, and committed inventory snapshot |
| `UAT-OST-008` | Positive | UI | Medium | Buckets overview and filters reconcile canonical asset counts | the unfiltered view shows three buckets and zero container-native assets |
| `UAT-OST-009` | Positive | UI | High | Bucket detail adopts Kubernetes unified header and evidence-labelled sections | the compact header separates bucket name and actual protection state from system provider and native type |
| `UAT-OST-010` | Negative | UI | High | Partial bucket observations never become fabricated zeros or Healthy | stale unavailable or unobserved evidence stays distinct from a genuinely observed zero |
| `UAT-OST-011` | Negative | Non-UI | High | Inventory direct URLs enforce source and actor authorization | the server rejects unauthorized request before revealing any source or bucket identity |

### Artifact Registry — Inventory, Security, Runtime & Governance (`UAT-REG-*`)

**Owning source:** app/artifact_registry/; #558. **Candidate test owner(s), not verified mapping:** tests/contracts/artifact_registry/; tests/unit/artifact_registry/; tests/integrations/. **Shared preconditions:** Registered registry with committed sync evidence; isolated Harbor/sandbox integration when approved.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-REG-001` | Positive | Both | High | Operator inspects registry/artifact inventory and synchronized evidence | Correct registry/project/artifact/version identity, freshness and pagination |
| `UAT-REG-002` | Negative | Both | High | Security vulnerability scan is absent, failed or partial | Unknown/partial posture not labeled Secure/Healthy |
| `UAT-REG-003` | Negative | Both | High | Runtime image binding is unresolved or cluster evidence is stale | Do not claim verified artifact-to-runtime association or false Ready |
| `UAT-REG-004` | Positive | UI | Medium | User opens Runtime Usage topology/detail and applies scoped filters | Links/tabs/modal and filter states work with canonical responsive layout |
| `UAT-REG-005` | Negative | Non-UI | High | Registry provider disabled or sync failed after earlier success | Latest committed source state truthfully supersedes old Ready evidence |

### Integrations — Registry, Provider Configuration & Runtime (`UAT-ING-*`)

**Owning source:** app/integrations/README.md. **Candidate test owner(s), not verified mapping:** tests/integrations/; tests/contracts/integrations/; tests/ui/. **Shared preconditions:** Provider-neutral registry fixtures including Kubernetes, Metrics Source, Alertmanager and Object Storage; no live secrets.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-ING-001` | Positive | Both | High | Operator registers an allowed provider instance and validates it | Capability-first domain/instance identity, sanitized connection readiness and audit |
| `UAT-ING-002` | Negative | Both | High | Invalid endpoint, TLS/certificate or credentials supplied | Validation fails without silently choosing other provider or leaking secrets |
| `UAT-ING-003` | Negative | Non-UI | High | Disabled or stale provider still has previously committed metrics | Consumers cannot represent it as active/Ready or silently substitute data |
| `UAT-ING-004` | Positive | UI | Medium | Navigate Integrations Overview → capability → instance detail and actions | Tabs, validation states, badge, modal and HTMX fit Violet standard |
| `UAT-ING-005` | Negative | Non-UI | High | Metrics/Alertmanager or Source Binding points to wrong cluster/instance | Reject cross-scope binding rather than fallback to default or another source |

### Notification Channels & Activity Center (`UAT-NTF-*`)

**Owning source:** app/platform_operations/notifications/; app/integrations/delivery/. **Candidate test owner(s), not verified mapping:** tests/integrations/notification_channels/; tests/contracts/integrations/; tests/ui/. **Shared preconditions:** Controlled channel fixture; disabled/failed delivery, permissions and stable event ID.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-NTF-001` | Positive | Both | Medium | Authorized operator configures supported notification channel | Safe configuration status, validation/audit and correct delivery eligibility |
| `UAT-NTF-002` | Negative | Non-UI | High | Delivery fails and retry/dedup encounters same event key | No false Delivered state, duplicate flooding or unbounded retry |
| `UAT-NTF-003` | Negative | Both | High | Channel disabled or unsupported provider is selected | Send is blocked or correctly marked ineligible; no silent fallback |
| `UAT-NTF-004` | Positive | UI | Medium | Notification Center tabs, filters, details and read-only activity links | Correct pagination, accurate status, accessible interactive disclosure |

### Intelligence — Recommendations, Alerts, Catalog & Automation Control (`UAT-INL-*`)

**Owning source:** app/intelligence/README.md. **Candidate test owner(s), not verified mapping:** tests/contracts/intelligence/; tests/unit/intelligence/; tests/ui/. **Shared preconditions:** Committed cross-domain findings and governed decisions; resolver execution disabled unless controlled sandbox approved.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-INL-001` | Positive | Both | High | Operator views recommendation and drilldown to impacted asset | Finding uses current committed evidence, exact source, scope and severity |
| `UAT-INL-002` | Negative | Non-UI | High | Finding source expires, clears or changes fingerprint | Old finding/advice cannot be presented as fresh authoritative risk |
| `UAT-INL-003` | Negative | Both | High | Unauthorized/unapproved actor attempts high-impact automation | Maker-checker/default-deny prevents execution and unauthorized escalation |
| `UAT-INL-004` | Positive | UI | Medium | Navigate Rule Catalog, Recommendations, Alert Intelligence and Control tabs | Accurate active/disabled/read-only states; HTMX, light/dark and responsive layout |
| `UAT-INL-005` | Negative | Non-UI | High | Alert normalization has partial or unavailable provider evidence | Unknown cannot be shown Healthy; duplicate cases and invented correlation prevented |

### Reports — Generate, Generated, Templates, Schedules & Storage (`UAT-RPT-*`)

**Owning source:** app/reports/README.md; docs/reports/kaori-reporting-standard-v1.md. **Candidate test owner(s), not verified mapping:** tests/reports/; tests/contracts/reports/; tests/ui/. **Shared preconditions:** Reports worker/queue and registered source in isolated test stack; test artifact storage with cleanup.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-RPT-001` | Positive | Both | High | Operator chooses valid cluster/source, format and generates report | Exactly scoped job and PDF/XLSX/CSV artifact with correct type and provenance |
| `UAT-RPT-002` | Negative | Both | High | Invalid output type, unselected cluster or unsupported report catalog requested | Reject; never silently switch cluster/type/renderer |
| `UAT-RPT-003` | Negative | Both | High | Reports worker unavailable, rendering or storage write fails | No false Generated/Ready; actionable job state and retained diagnostic evidence |
| `UAT-RPT-004` | Positive | UI | Medium | Generate wizard interacts with selectors, validation and progress | Expected step navigation, editable fields, loading/blocked/toast and responsive layout |
| `UAT-RPT-005` | Negative | Non-UI | High | Unauthorized principal opens Generated artifact or storage linkage | Permission-scope checks prevent disclosure even by direct URL |
| `UAT-RPT-006` | Negative | Non-UI | High | Schedule modified/deleted after run admitted | Run uses committed snapshot of accepted delivery intent, not mutable definition |
| `UAT-RPT-007` | Positive | UI | Medium | Browse Generated, Templates, Schedules and Storage registries | Scoped filters/pagination, detail handoff, evidence state, downloadable artifact metadata |

### Platform Operations — Overview, Jobs & Executions (`UAT-OPS-*`)

**Owning source:** app/platform_operations/README.md; app/platform_operations/jobs/. **Candidate test owner(s), not verified mapping:** tests/platform_operations/jobs/; tests/contracts/platform_operations/; tests/ui/. **Shared preconditions:** Known JobExecution history, policy scopes and isolated queue worker fixtures.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-OPS-001` | Positive | Both | Medium | Operator views Jobs registry, selects failed execution and reads details | Correct job owner, state, error evidence and link to owning capability |
| `UAT-OPS-002` | Negative | Non-UI | High | Job retry/cancel occurs during worker result race | No duplicate forbidden execution or false terminal status |
| `UAT-OPS-003` | Negative | Both | High | Worker/queue dependency unavailable or blocked | Correct blocked/degraded visibility, no invented execution success |
| `UAT-OPS-004` | Positive | UI | Medium | Platform Overview and Jobs tabs/filters/actions are exercised | Committed-only summary, appropriate permission scopes and canonical visual states |

| `UAT-OPS-005` | Positive | UI | Medium | Operations Overview presents committed workspace posture in compact cards | Three permissioned workspace cards show canonical domain status, three evidence metrics, compact one-line descriptions and source-owned navigation with a matching overall review posture |
| `UAT-OPS-006` | Positive | UI | Medium | Jobs configuration catalog and schedule controls retain operational context | The selected job follows the URL and HTMX navigation, search count updates, schedule controls and one-line Scope remain aligned, and the Guide opens above the footer without a horizontal scrollbar |
| `UAT-OPS-007` | Positive | UI | Medium | Report dispatcher shows compact committed delivery channels | The bounded keyboard-scrollable channel rows show names, statuses, singular or plural count and an explicit empty state without oversized cards or additional provider requests |
| `UAT-OPS-008` | Positive | UI | High | Guarded empty-inventory recovery guidance stays adjacent and manual | Shared Violet cards retain the manual-only warning and full fail-closed Guide beside the title; the CONFIRM EMPTY challenge, CSRF and verification action remain identifiable but unexecuted |
| `UAT-OPS-009` | Negative | Both | High | Overview reflects scheduler policy dispatch failure without an execution | Jobs posture is Needs Attention and the policy attention remains visible without fabricating completed or active executions; only persisted read models are queried |
| `UAT-OPS-010` | Negative | Both | High | Restricted role cannot reach unauthorized Operations Overview content | Configure-only access does not grant Overview, view-only and mixed roles see only permitted workspace cards and links, and no restricted data or actions leak |
| `UAT-OPS-011` | Negative | Non-UI | High | Guarded reconciliation fails closed on mismatched provider discovery | Provider mismatch or changed snapshot rejects reconciliation and preserves the committed inventory without deleting records or claiming success |
| `UAT-OPS-012` | Negative | UI | Medium | Unfinished feature-cycle controls remain transparently unavailable | Disabled status remains truthful, the UI does not imply a completed or executable capability, and no mutation or fake success is recorded |

### Platform Operations — Data Lifecycle & Secret Reveal (`UAT-LIF-*`)

**Owning source:** app/platform_operations/data_lifecycle/; app/platform_operations/kubernetes/. **Candidate test owner(s), not verified mapping:** tests/contracts/platform_operations/; tests/platform_operations/; tests/security/kubernetes/. **Shared preconditions:** Archive destination, retention policies, isolated lifecycle artifacts and explicit secret-reveal authorization.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-LIF-001` | Positive | Both | High | Operator previews lifecycle policy and executes approved archive-first run | Verified archival evidence precedes governed cleanup; JobExecution/audit consistent |
| `UAT-LIF-002` | Negative | Non-UI | High | Archive verification fails, destination missing or artifact is partial | Destructive cleanup blocked and recoverable original data preserved |
| `UAT-LIF-003` | Negative | Both | High | Unapproved/expired reveal request tries to access secret | Fail closed; only authorized one-time disclosure, never routine leakage |
| `UAT-LIF-004` | Positive | UI | Medium | Kubernetes Admin Overview and Secret Reveal workspace navigation | Committed posture, deep links and inline policy editor remain scoped without Secret disclosure |
| `UAT-LIF-005` | Negative | Both | High | Lifecycle attempt duplicates during policy update or failure | No duplicate destructive job or false archived/cleaned claim |
| `UAT-LIF-006` | Positive | UI | Medium | Namespace Policy pagination, search and filters retain canonical state | numbered pagination preserves its selected page across HTMX updates and reload |
| `UAT-LIF-007` | Negative | UI | Medium | Cancel discards an unsaved namespace policy change | the inline editor closes with no committed change |
| `UAT-LIF-008` | Positive | Both | High | Approved Harbor policy save and rollback preserve audit correlation | the enabled namespace count rises from two to three and returns to two |
| `UAT-LIF-009` | Negative | Both | High | Viewer direct requests cannot read Kubernetes Admin configuration | the server denies both unauthorized read requests |
| `UAT-LIF-010` | Negative | Non-UI | High | Unauthorized or missing-CSRF policy POST cannot commit changes | the server rejects each unauthorized request |
| `UAT-LIF-011` | Negative | Both | High | Unavailable namespace source and unready clusters fail closed | source Unknown is distinct from an authoritatively Missing namespace |
| `UAT-LIF-012` | Positive | UI | Medium | Audit Warning presents successful namespace restriction as attention | the Success record retains its before and after changes and event key |
| `UAT-LIF-013` | Positive | UI | Medium | Kubernetes Admin responsive visual and keyboard coverage | focus order and accessible control labels remain correct |

| `UAT-LIF-014` | Positive | UI | Medium | Lifecycle nine-domain navigator and boundary Guide remain consistent | Domain selection and count remain consistent across navigation, responsive cards preserve selected state, and the Execution Boundary Guide opens above a one-row no-scroll footer |
| `UAT-LIF-015` | Positive | Both | High | Archive Only preserves verified artifacts and audit evidence | Verified archive/manifests and audit evidence are retained, records remain governed without unapproved purge, and the operator sees an attributable outcome |
| `UAT-LIF-016` | Positive | UI | Medium | Archive Storage and History remain readable without extra mutation | Storage guidance and bounded history rows remain readable, pagination/search preserve context and read-only evidence does not initiate cleanup |
| `UAT-LIF-017` | Negative | UI | Medium | Paused lifecycle adapters are not mistaken for admitted cleanup | Paused/disabled posture remains explicit and no archive, retention or destructive action is presented as admitted or automatically successful |
| `UAT-LIF-018` | Negative | Both | High | Unverified archive or unauthorized lifecycle mutation preserves source | The server rejects the request or blocks cleanup, reports an actionable state, and retains committed original records and independent archive evidence |

### Welcome Workspace Catalog (`UAT-WEL-*`)

**Owning source:** app/welcome/, app/templates/welcome/ and app/templates/components/. **Candidate test owner(s), source-reviewed only:** tests/welcome/; tests/security/welcome/; tests/e2e/welcome/; tests/ui/test_representative_interactions.py. **Shared preconditions:** Authorized test identities with known effective RBAC; deterministic browser, canonical viewports and approved visual signatures. **UAT evidence:** #746 screenshot and HTTP 403 manual records, not Gherkin machine PASS.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-WEL-001` | Positive | UI | Medium | Authenticated user visits both / and /welcome | Canonical Welcome displays role, catalog and shared shell without live provider queries |
| `UAT-WEL-002` | Positive | Both | High | Super Admin and Viewer open role-filtered Welcome separately | Cards/counts match effective RBAC, forbidden cards absent from Viewer HTML, Settings available |
| `UAT-WEL-003` | Positive | UI | Medium | Permitted user searches for tenant | Only Tenant Management remains, result count 1, other groups hidden |
| `UAT-WEL-004` | Negative | UI | Medium | Unmatched workspace search then Escape | Shared zero-result empty state, Escape restores permitted cards and releases input focus |
| `UAT-WEL-005` | Positive | UI | High | Light/dark Welcome is rendered across canonical responsive viewports | Hero/cards/actions fit with approved visual-baseline checks; no silent rebaseline |
| `UAT-WEL-006` | Positive | UI | Medium | User clicks an authorized Open Workspace card | Correct destination loads with independent server authorization |

### Shared Shell, Settings, Visual QA & Accessibility (`UAT-UIX-*`)

**Owning source:** docs/standards/KAORI_ENGINEERING_STANDARD_V1.md; #222; #543. **Candidate test owner(s), not verified mapping:** tests/ui/; tests/rendering/; tests/contracts/design/; tests/settings/. **Shared preconditions:** Deterministic authenticated browser fixture, reviewed screenshot baselines and six canonical viewport sizes.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-UIX-001` | Positive | UI | Medium | Login and navigate sidebar, tabs, breadcrumb and global actions | Correct active destination, responsive drawer, keyboard accessibility and history |
| `UAT-UIX-002` | Negative | UI | High | Open long modal/drawer and trigger form validation at 360×800 / 390×844 | No clipped actions, document overflow, lost focus or inaccessible error |
| `UAT-UIX-003` | Positive | UI | Medium | Switch light/dark and revisit page/overlay across canonical viewports | Theme persisted, Violet/shared components and text contrast remain legible |
| `UAT-UIX-004` | Negative | UI | High | Rendered Hero/card/table/filter/notification geometry deviates from approved baseline | Executable geometry/visual assertion fails with screenshot/trace, never auto-baselines |
| `UAT-UIX-005` | Negative | UI | Medium | Empty/loading/error/blocked state and pending HTMX action appear | Correct shared semantic state and recoverability; no misleading empty success |
| `UAT-UIX-006` | Positive | UI | Medium | Change pagination rows 5→10, filter and Clear Filters | Reset to page 1, preserve Rows and correct HTMX target and loading |
| `UAT-UIX-007` | Negative | UI | High | Mandatory UI base URL or authenticated browser fixture is unavailable | Scenario reports SKIP/BLOCKED, not a UAT execution PASS |

### Release & Server UAT Operational Evidence (`UAT-REL-*`)

**Owning source:** docs/engineering/KAORI_DELIVERY_WORKFLOW.md; #619; #1710. **Candidate test owner(s), not verified mapping:** tests/contracts/release/; tests/integration/release/. **Shared preconditions:** Admitted staging SHA and exact OCI digest, approved server UAT runbook and non-destructive access.

| Scenario ID | Type | Layer | Risk | Given / When | Then: expected observable outcome |
| --- | --- | --- | --- | --- | --- |
| `UAT-REL-001` | Positive | Non-UI | High | Deploy exact accepted image and inspect health, workers and release identity | Healthy readiness, matching SHA/digest, migration and rollback evidence |
| `UAT-REL-002` | Negative | Non-UI | High | Wrong/stale OCI digest or unaccepted candidate is submitted | Deployment/promotion fails closed without mutating current accepted release |
| `UAT-REL-003` | Negative | Non-UI | High | Migration/readiness/recovery precondition fails in controlled drill | No false UAT PASS or release advance; restore/roll-forward evidence correct |
| `UAT-REL-004` | Positive | UI | Medium | Operator performs bounded hosted-UI smoke on deployed UAT image | Login/navigation, critical screens, responsive states and user-visible feedback work |

## Additional UI-state coverage matrix (apply to affected scenarios)

All six #222/#543 viewports remain canonical: 1440×900, 1280×800, 1024×768, 768×1024, 390×844, 360×800. Exercise **light and dark** as relevant. Select expensive full screenshot matrix for intentional staging/UAT audit, while a representative changed-path matrix is allowed for Developer Check after governing approval. Test at least these state transitions per applicable page: initial/normal → interaction (click/filter/submit/modal) → success; invalid input → inline error; permission denied; zero data; loading; runtime failure/blocked/degraded; recovery. Validate shared Hero, table/pagination default 5, action/validation/HTMX, overlay viewport safety, accessible focus/keyboard, semantic state, and no unauthorized page-local style variants.

**Visual acceptance is not inferred** when a screenshot matches a poor or unreviewed baseline. Approved baselines are not overwritten automatically. Real-device UAT is additive and cannot be inferred from virtual viewport output.

## Evidence and reviewer usage

For each scenario execution, reuse the #1725 record contract: Scenario ID, owning requirement/Issue, selected exact source SHA/tree, release OCI digest if deployed, test node ID, runner/tester, environment and fixtures, intended input/steps, assertions vs actual result, PASS/FAIL/BLOCKED/NOT RUN/N/A or runner SKIP, screenshot/trace/JUnit/audit/DB/provider reference, cleanup evidence, defect/retest lineage, and separately named human reviewer/time/decision. **A candidate directory or an earlier unrelated CI PASS is not scenario-level UAT evidence.**

After a real run, record actual evidence in the owning Issue/PR comment and keep the specification stable. Create bounded remediation issues for detected defects, linked to the scenario; add the narrowest permanent regression assertion and rerun the affected tests against the corrected exact candidate. Do not automatically promote or close based on automated PASS.

## Open inventory gaps and next steps

1. **Route completeness is unverified:** compare this baseline with the exact Flask route inventory and active navigation/permission manifest after review-branch admission; review parameterized detail routes, auxiliary screens, provider capability gates, and hidden/unreachable pages. No '100% route coverage' assertion yet.
2. **Executable mapping is partially inspected, never executed:** see [KAORI_UAT_TEST_MAPPING_AUDIT.md](KAORI_UAT_TEST_MAPPING_AUDIT.md) for a first-wave source assertion review (9 PARTIAL, 5 SOURCE-CONTRACT ONLY; no scenario-level UAT PASS). Inspect remaining pytest/Playwright node IDs/assertions for each scenario; identify missing UI interactions and negative paths; implement under #1726 (UI) and #1727 (non-UI). Do not count file existence or static source contracts as behavior coverage.


3. **Conditional infrastructure:** Native real-provider tests need approved disposable Namespace; Capsule tests depend on an approved compatible cluster and must remain BLOCKED or not applicable with reviewer rationale. Real secret/reveal, destructive retention, deployment rollback and privileged mutation need separately authorized runbooks.
4. **CI/UAT gate not changed:** #1728 will enforce mandatory coverage and evidence integrity after scope is agreed; this document adds **no new runner or workflow trigger**.
5. **Human acceptance outstanding:** #1730 owns selected end-to-end pilot and explicit reviewer acceptance of exact staging SHA/digest. An accepted local DevContainer review is not assumed to cover all listed scenarios.
6. **Snapshot drift:** compare reviewed candidate and eventual admitted staging code. Planned/disabled behavior is tested as correctly unavailable; do not assume all source classes are end-user features.

