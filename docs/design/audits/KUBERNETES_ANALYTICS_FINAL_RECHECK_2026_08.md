# Kubernetes Analytics Final Recheck — August 2026

**Status:** Targeted fixes applied; authoritative devcontainer validation and browser regression pending.

## Scope

This final recheck covers Analytics Overview, Resource Utilization, Capacity, Storage, Workload, Forecast, Top Consumers, and Alerts & Anomalies. The accepted KAORI Violet presentation remains the baseline; redesign is limited to concrete interaction/standardization defects found during final review.

## Primary findings and disposition

### 1. Analytics tab state had two owners

Analytics templates used Alpine `activeTab` visibility bindings while `app/static/js/kubernetes/analytics/controls.js` independently handled click, keyboard navigation, native `hidden`, persistence, lazy activation, and HTMX rehydration. That dual ownership made tab state vulnerable to being reset or visually desynchronized.

**Disposition:** Analytics Content Tabs now have one native controller. Templates provide server-readable initial `hidden` state only; `analytics_controls.js` owns subsequent tab activation.

### 2. Overview leaked internal identifiers into the visible tab row

Overview tab tuples also carry section keys, DOM targets, and load mode. The old Analytics compatibility wrapper passed those tuples to shared Content Tabs, where tuple element four was interpreted as a badge. Internal values such as `resource-snapshot`, `capacity-snapshot`, and `top-consumers` therefore appeared in the UI and forced the row to wrap.

**Disposition:** Overview disables badges, uses the shared no-wrap mode, and uses concise user-facing labels:

`Usage · Capacity · Workload · Storage · Consumers · Forecast · Alerts · Actions · Guidance`

Internal materialization identifiers remain runtime metadata only. Narrow viewports scroll horizontally rather than creating a second tab row.

### 3. Shared tab palette and JavaScript had drifted

The shared Content Tabs component and Analytics JavaScript each carried their own active/inactive Tailwind class lists. The two lists no longer matched exactly, so a panel could switch while its tab retained conflicting visual classes.

**Disposition:** `components/content_tabs.html` is the sole owner of active/inactive visual class tokens. The rendered tab exposes those tokens through data attributes and `analytics_controls.js` only applies that contract.

### 4. Compatibility/dead ownership remained

The following current-release surfaces had no justified owner:

- `app/templates/analytics/components/_content_tabs.html` — backward-compatible wrapper over the shared Content Tabs component;
- `app/templates/analytics/components/_snapshot_panel.html` — orphan template;
- `app/templates/kubernetes/analytics/materialization/_freshness.html` — orphan materialization fragment;
- `stabilizeAlertsAfterSwap` / `data-alerts-tabset` — orphan Alpine-era Alerts rehydration bridge.

**Disposition:** all are retired. Analytics consumes shared components directly.

Provider fallback terminology that represents an actively supported source policy, such as Alertmanager → Prometheus alert fallback, is not obsolete compatibility and remains supported.

### 5. Materialized read paths retained runtime compatibility repair

Cluster snapshot decoding could query the database when old serialized cluster metadata was incomplete. Forecast reprojection copied a historical payload and then deleted obsolete derived keys.

**Disposition:** materialized decode is now ORM-free and requires canonical embedded cluster identity metadata. Forecast reprojection constructs a fresh canonical resource payload directly. Old materialization shapes are refreshed, not repaired through compatibility code.

### 6. Snapshot identity helpers were coupled to the Flask/SQLAlchemy service module

Parameter normalization and fingerprinting are deterministic leaf logic but lived inside `materialization/service.py`, which made isolated Unit evidence unnecessarily dependent on application infrastructure.

**Disposition:** canonical snapshot identity is owned by dependency-light `materialization/identity.py`. Service, worker, and job-adapter callers consume that leaf module.

### 7. Refresh-error UI could expose the stored worker error string directly

The materialization presentation layer already parses worker failure records into operator-safe title/detail/remediation fields, but the shared Analytics workspace rendered `snapshot.last_error` directly.

**Disposition:** the workspace renders only parsed title/detail/remediation fields. Recommended remediation uses the shared Analytics interpretation primitive; the raw stored error is not rendered directly.

### 8. Explicit final-recheck evidence was incomplete

Analytics had extensive historical contracts but did not have a clearly registered L0–L7 release evidence set comparable with the already reviewed domains.

**Disposition:** permanent Contract, Unit, Functional, Integration, Security, Rendering/UI, E2E, and final-lock evidence is registered.

## Canonical Content Tabs runtime

```text
shared components/content_tabs.html
        ↓
server-readable initial active tab/panel
        ↓
analytics_controls.js
        ↓
click + Arrow Left/Right + Home/End
        ↓
aria-selected + roving tabindex
        ↓
shared active/inactive class contract
        ↓
native hidden panel state
        ↓
URL/session persistence
        ↓
kaori:analytics-tab-activated
        ↓
first-use HTMX materialization only
```

Nested tabsets resolve buttons and panels through the nearest `data-analytics-tabset`, so a nested Top Consumers CPU/Memory/PVC/Pods tab cannot mutate the parent Rankings/Records/Recommendations tabset.

## Shared tab standard

Content Tabs are now formally registered as **Tab Style 4 — Content Tabs** in `docs/design/components/TAB_STYLES.md`, with the detailed contract in `docs/design/components/CONTENT_TABS.md`.

Use Content Tabs for several closely related views inside one established workspace. They are not a replacement for Integrated Workspace Tabs, Framed Workspace Tabs, or Compact Segmented Tabs.

## Security and data boundary

- Every user-facing Analytics route remains protected by `analytics.view`.
- Route modules do not execute Prometheus or Alertmanager provider queries directly.
- Heavy evidence is worker-owned and committed to `AnalyticsSnapshot`; browser requests consume materialized read models.
- HTMX-only fragment routes retain their full-page navigation boundary.
- Refresh failures render parsed operator-safe detail/remediation, not raw stored worker errors.
- Materialized snapshot decoding is ORM-free and does not perform hidden database repair queries.

## Performance and reliability

- hidden tabs do not execute browser-time provider queries;
- lazy sections hydrate on first activation through an HTMX `once` trigger;
- URL/session state survives normal tab navigation without page reload;
- nested tabsets are scoped independently;
- current snapshot identity is deterministic from canonical ordered parameters;
- unavailable evidence remains Unknown/N/A rather than synthetic zero or Healthy;
- current source-health failures continue to preserve the previous committed snapshot while exposing controlled failure evidence;
- the worker source lock and provider query-runtime evidence remain worker-owned, not presentation-owned.

## UI, accessibility, and responsive contract

- KAORI Violet remains the navigation/identity accent; semantic colors are state-only.
- Content tab icons are decorative and `aria-hidden`.
- tab controls use `role="tab"`, `aria-controls`, `aria-selected`, and roving `tabindex`;
- panels use `role="tabpanel"` and `aria-labelledby`;
- the server renders a readable default panel before JavaScript executes;
- Overview uses one-row compact navigation at the 14-inch target; narrow viewports use horizontal overflow;
- no Analytics page-local inline event handlers/styles are introduced;
- shared Hero and Dark Mode verifiers remain green in source review.

## Architecture and maintainability

Canonical web boundary:

```text
route
→ Analytics application/presentation service
→ materialized snapshot read model
→ Jinja presentation
```

Canonical worker boundary:

```text
scheduled/manual materialization
→ provider consumer
→ normalized domain payload
→ canonical serialization
→ AnalyticsSnapshot
```

Snapshot normalization/fingerprinting lives in `materialization/identity.py`; serialization does not re-enter the ORM on decode. The current `app/analytics` package is the release owner. No parallel package, import shim, or compatibility wrapper is introduced during final recheck.

Known global code-health/UI debt outside Analytics is not rebaselined by this review. Analytics-specific code-health changes must not expand the repository's approved debt ledger.

## Release evidence

- **L0 Static Quality:** canonical quality gate + `verify_analytics_final_lock.py`
- **L1 Contract:** `tests/contracts/analytics/test_analytics_final_release_contract.py` plus the existing Analytics contract suite
- **L2 Unit:** `tests/unit/analytics/test_materialization_identity.py`
- **L3 Functional:** `tests/analytics/test_kubernetes_analytics_page_flows.py` plus existing Analytics behavior tests
- **L4 Integration:** `tests/integration/analytics/test_materialized_snapshot_read_model.py`
- **L5 Security Regression:** `tests/security/analytics/test_analytics_security.py`
- **L6 Rendering/UI Contract:** `tests/rendering/analytics/test_analytics_rendering.py`
- **L7 End-to-End Smoke:** `tests/e2e/analytics/test_analytics_smoke.py`

Source-level final-recheck evidence in the audit workspace:

- full Analytics Contract suite: **271 passed**;
- dedicated Unit/Security/Rendering source evidence: **8 passed**;
- all current Analytics Jinja templates parse successfully;
- Analytics final-lock verifier: **PASS**;
- Analytics Compact Label verifier: **PASS**;
- Analytics PDF Publication verifier: **PASS**;
- Hero standard: **PASS**;
- Dark Mode standard: **PASS**;
- source hygiene: **PASS** after runtime caches are removed.

Authoritative Flask/SQLAlchemy Functional, Integration, E2E, Ruff, djLint, Pyright, Prettier, frontend build, and full release-gate results must come from the project devcontainer.

## 2026-08-11 semantic contract normalization

The final source review found eight Analytics contract failures caused by stale formatter or implementation fingerprints rather than runtime regressions. The contracts were normalized to preserve the same operational semantics while tolerating canonical Ruff/djLint quote and whitespace changes.

The normalized guards now explicitly retain:

- Alerts `Watch` / warning posture when warning, anomaly, or incomplete evidence is present;
- shared `table_label` semantic tone ownership for Analytics guidance surfaces;
- null-safe Forecast warning/critical threshold evaluation through `item.get(...)` and `_float(...)`;
- the `Not Recorded` Prometheus checked-at fallback through `user_datetime`;
- PVC pressure used/capacity `N/A` fallbacks under partial evidence;
- CPU/Memory/Pods Utilization legend role and tone ownership independent of formatter spacing; and
- Workload table boundaries that keep long recommendation/evidence descriptions in View Details instead of dense record cells.

After normalization, the full Analytics contract suite passes **271/271** and the dedicated Unit/Security/Rendering source evidence passes **8/8**. Functional, Integration, and E2E execution remains authoritative in the project devcontainer because the audit runtime does not include Flask/Flask-Login.

## Lock condition

Analytics remains **TARGETED FIX — AUTHORITATIVE VALIDATION PENDING** until all L0–L7 suites, browser review (Light, Dark, 14-inch, narrow viewport), and `bash scripts/quality_gate.sh --all` are green. No version bump occurs during this domain review.

## 2026-08-15 page-copy and boundary audit

This pass rechecked all eight Kubernetes Analytics workspaces after the Kubernetes Inventory/Governance/Operations review. The existing dependency blocker presentation remains the accepted baseline and was not redesigned.

### Copy refinement

The review keeps user-facing copy concise while making the worker/materialization boundary explicit where a full-page pending or blocked state needs explanatory text:

- Analytics Overview now names resource utilization, workload posture, storage, forecasts, top consumers, and alert signals.
- Capacity pending/blocked copy describes shared capacity, allocation, and headroom results.
- Storage pending/blocked copy states that committed operational snapshots are prepared by the analytics worker and reused across viewers.
- Workload pending/blocked copy states that committed quota, runtime, and resource snapshots are worker-prepared and reused across viewers.
- Forecast pending/blocked copy is shorter and explicitly keeps horizon, model, and resource tabs presentation-only.

### Runtime and ownership findings

The audit reconfirmed the current release boundaries:

- all Kubernetes Analytics full-page and fragment routes remain protected by `analytics.view`;
- route modules do not issue Prometheus/Thanos or Alertmanager queries directly;
- expensive analytics evidence remains worker-owned and is read through committed materialized snapshots;
- stale/previous committed evidence can remain visible while source readiness is degraded, with source-warning evidence kept separate from the committed payload;
- Overview lazy-loads one operational domain at a time instead of materializing every hidden tab on the initial request;
- Utilization summary, trend, and node detail retain separate materialization ownership so hidden detail tabs do not expand the initial provider workload;
- Forecast snapshot identity remains limited to committed-history dimensions (`cluster`, `namespace`, `history_window`); horizon, model, and resource-tab changes are local reprojection/presentation state;
- Top Consumers and Alerts HTMX fragments retain their full-page navigation boundary and do not bypass dependency evaluation;
- missing evidence remains `Unknown`/`N/A` rather than synthetic zero or Healthy.

### Template and release integrity

Source audit evidence for this pass:

- 85 Python modules under `app/kubernetes/analytics` parse successfully;
- 395 literal Analytics template references resolve with zero missing targets;
- Kubernetes Analytics contract suite: **298 passed**;
- `verify_analytics_final_lock.py`: **PASS**;
- Hero standard: **PASS**;
- Dark Mode standard: **PASS**.

The shared Analytics compact-label verifier also exposed two pre-existing Object Storage Analytics presentation drifts during this pass: a count-only bucket metadata badge still carried a database icon, and Operational Metrics Readiness passed an icon into the compact status label. Both were normalized to the shared text-first compact-label standard so the release-wide Analytics verifier remains green.

Functional page-flow import evidence still requires the project devcontainer because the audit runtime does not include Flask. The dependency blocker design itself remains unchanged by this pass.
