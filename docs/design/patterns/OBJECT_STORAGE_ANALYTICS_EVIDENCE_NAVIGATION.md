# Object Storage Analytics — Central Data & Evidence Navigation

## Authority and design decision (October 2026 UAT)

Human-approved design review #3235; implementation issue #3260. This governs **Object Storage Analytics presentation only**. Keep August 2026 Object Storage provider-neutral materialization, committed Inventory prerequisites, forecast-worker ownership, source-resolution boundaries and RBAC authoritative. Do not clone providers or issue live provider requests for normal page load.

**Single audit destination:** Analytics Overview → `Data & Evidence` (internal tab key remains `evidence`). The five owning workspaces no longer repeat generic Evidence tabs. Instead they reuse a compact, source-bound `_domain_evidence_context.html` banner linking directly to the central tab.

## Shared navigation

- Direct link uses `url_for('analytics.object_storage_overview', system_id=system.id, time_range=selected_time_range, tab='evidence')`; preserve canonical system identity and selected time window.
- Existing shared `app/static/js/analytics/controls.js` reads `URLSearchParams.get('tab')` and selects the matching Overview tab. No new domain-only tab JavaScript or new CSS.
- Preserve keyboard access, focus, responsive and dark/light styling through canonical `content_tabs.html`, Violet tokens and shared status labels.

## Evidence placement

| Workspace | Evidence visible in context | Deep detail |
| --- | --- | --- |
| Analytics Overview | Single `Data & Evidence` tab; Operational Metrics Contract; committed source authorities; readiness; missing/non-applicable state; full audit reconciliation | Owned centralized panel |
| Capacity & Usage | Committed snapshot source/status banner; `View Reconciliation` action | Native read-only Reconciliation dialog via shared dialog controller; `Quota & Buckets` owns quota/usage field evidence |
| Performance | Committed metrics-source/status banner | `Request Health`, `Traffic & Trend`, `Bucket Activity` |
| Top Consumers | Committed metrics-source/status banner | `Consumer Records` and activity records with per-field provenance |
| Forecast | Worker-materialized forecast state in context | `Worker & Method` retains generation/refresh/methodology; charts distinguish observed history from projection |
| Alerts & Anomalies | Alertmanager-first resolved source/status in context | `Alert Overview` → expandable Alert Source & Lifecycle Details; provider alerts and KAORI anomaly signals remain separate |

## Semantic and security guardrails

- Provider/source stays authoritative; KAORI normalizes and reads **committed** evidence.
- Unknown, Not Configured, No Current Samples, Metric Not Scraped, Runtime Query Failed, unavailable worker materialization and stale states must never become fabricated zeros or healthy postures.
- Metrics Source `ALERTS` is narrower than Alertmanager lifecycle; preserve the original source-reconciliation semantics.
- RBAC remains `object_storage_analytics.view`; no new routes, permissions, workers, models or schema.
- Existing legacy shared Evidence partials remain in repository for other consumers; they are no longer duplicated in the five workspaces. Cross-domain adoption requires separate design review.

## UAT acceptance

Validate one central tab; five domains without duplicate Evidence tabs; context status/source and link with `system_id`, `time_range`, `tab=evidence`; Capacity Reconciliation modal; Forecast worker metadata; Alerts fallback detail; missing/partial states. Validate 6h and 24h, narrow/desktop and light/dark, keyboard/hover, real HTTP 200, and source formatting/pytest. This document does not equate static contract success with completed browser UAT.

Workstream delivery: issue #3260 → branch/commit → review PR to temporary `kaori/review/staging-uat` → operator UAT/acceptance. Official CI/CD, Full Admission, promotion and release remain on HOLD pending explicit user approval.

## Gherkin — UAT acceptance scenarios (pending operator execution)

```gherkin
Feature: Central Object Storage Analytics Data & Evidence

  Scenario: Data & Evidence exists only on Overview
    Given an Object Storage system has committed Inventory and Analytics evidence
    When I open Analytics Overview
    Then I see one "Data & Evidence" tab
    And its view includes metric contract, source authority, readiness, and reconciliation
    When I open Capacity, Performance, Top Consumers, Forecast, or Alerts
    Then I do not see a generic "Evidence" tab in those five workspaces
    And I see the contextual committed evidence state and source

  Scenario: Domain link selects the correct system and analysis window
    Given I selected an Object Storage system and a 6h time range
    When I activate "View Data & Evidence" from any owning workspace
    Then Analytics Overview opens with the same system identity
    And the selected 6h window is preserved
    And "Data & Evidence" is selected by the existing tab controller

  Scenario: Domain-specific evidence is preserved
    Given I open Capacity Summary
    When I activate "View Reconciliation" beside "View Data & Evidence"
    Then an accessible read-only modal displays committed Inventory and operational comparison
    Given I open Forecast Worker & Method
    Then I see the committed worker generation status and methodology
    Given I open Alerts Overview
    When I expand "Alert Source & Lifecycle Details"
    Then I can distinguish Alertmanager lifecycle evidence from narrower Metrics Source ALERTS fallback
    And KAORI anomaly signals remain independent of provider-alert records

  Scenario: Unavailable evidence never becomes fabricated healthy data
    Given a source has no samples, is stale, or a worker query failed
    When I review any Object Storage Analytics workspace and the central Evidence view
    Then source-specific Unknown, partial, stale, or failed status remains visible
    And I do not see missing evidence represented as zero or Healthy

  Scenario: Accessible and responsive operation
    Given I am using keyboard navigation in light or dark mode
    When I select a content tab, a domain evidence link, or a collapsed source detail
    Then focus and selection state remain visible
    And the content remains usable at desktop and narrow widths
    And page requests do not raise a Jinja error or HTTP 500
```


## 26 October 2026 — Evidence visual UAT refinement

- Source-authority descriptions and fallback rules use concise single-line copy at the desktop UAT viewport; retain full values in title attributes where clipping is necessary on narrower screens.
- Committed Domain Coverage uses the existing table primitives and compact semantic status labels in four accessible columns: Domain, Committed Source, Readiness, Fallback Boundary. Color reflects each committed tone, never inferred health.
- Inventory & Operational Reconciliation uses a single comparison table with Operational, Inventory, combined Delta/Variance as Drift, and semantic Assessment; embedded rendering hides redundant nested titles inside the Overview/Capacity disclosures. No committed metric arithmetic or evidence source has changed.
- Gherkin visual QA: at 1440px verify one-line authority and boundary explanations, four semantic readiness badges, and legible Drift with both original delta and variance. At narrow viewports verify horizontal overflow rather than information loss, and keyboard accessibility of Overview's disclosure and Capacity's modal.

## 26 October 2026 — Capacity Summary human UAT refinement (#3277)

- Title-adjacent `Capacity Operating Boundary` uses the canonical `info_tip.render(..., variant='guide')` with committed vs Inventory, physical headroom vs quota, and historical growth vs forecast boundaries. Visible posture, source and measurement values are unchanged.
- Remove the redundant healthy-path Usage Direction paragraph. Missing/insufficient historical samples still receive their existing explicit warning, not fabricated growth.
- In Capacity only, move Inventory & Operational Reconciliation from the bottom Summary disclosure into a read-only browser-native dialog. Its **View Reconciliation** trigger sits beside **View Data & Evidence** in the shared contextual evidence banner; both use identical action styles. The existing global `native_dialogs.js` owns focus, Escape, backdrop and close. Dialog body retains the shared Reconciliation table and embedded no-duplicate-heading mode; Overview's evidence disclosure remains unchanged.
- UAT: verify open/close, focus restoration, 6h/24h source context, full Drift delta+variance and source-based Assessment, desktop/mobile table scrolling, light/dark, keyboard, no HTTP 500 or provider mutation. This is a human-review candidate until exact-head checks and actual browser evidence are recorded.

## 26 October 2026 — Capacity Trend and Quota Records UAT polish (#3282)

- Standalone Capacity `Usage Trend` and `Quota & Buckets` section titles gain canonical KAORI title-adjacent Info Tip Guides. Overview's existing Guide variants and historical/forecast semantics remain unchanged.
- Four standalone observed-trend facts retain exact committed values but add shared semantic icon roles: sample count (brand), direction/change (committed trend tone), growth/day (informational insight). Increasing usage does not imply provider health or an automatic capacity alert.
- Capacity Bucket Records uses concise desktop single-line context copy while retaining bounded Inventory fallback; Performance and Top Consumers descriptions remain unchanged.
- The filter bar reuses the canonical responsive table filter geometry and adds **Quota State** and **Quota Pressure** selectors for Capacity only. Configured/Not Configured/Unknown derive from committed quota state/evidence; Within (under 85%), Pressure (85% to under 95%), and Critical (95% or above) require usable configured quota and utilization data. Search, system identity, time range, tab and Rows persist across HTMX and pagination; filtering resets page to 1, and Clear Filters retains Rows.
- Dev Container UAT must confirm 6h/24h, 1440px one-line description, 390px wrapping, light/dark, keyboard Guides, valid/invalid/empty filter combinations, pagination, Clear Filters, no false Unknown-as-zero outcomes and no HTTP 500.

## 26 October 2026 — Capacity Bucket Records UAT follow-up (#3282)

- The Capacity-only Bucket Capacity Records header uses `table_ui.block_icon_classes()` with the `boxes` icon, next to the title/result count and the existing concise source-bound description.
- **Clear Filters** is a right-hand header action, consistent with the existing Provider Alert Records table. It reuses `registry_ui.clear_filters_action` with `lead=false`; no `order-first` is introduced in the form. The filter bar itself contains Search Bucket, Quota State, and Quota Pressure only.
- Clear retains the canonical system/time-window/tab/Rows context and HTMX table refresh; no provider query, additional classification, or backend mutation is introduced.
- Latest operator checkpoint before this follow-up: 36 focused pytest PASS; `djlint` formatting debt on Trend, `ruff I001` on quota filter test imports, and `ruff format` on quota filter predicate remained. Those formatter-only findings were addressed in the follow-up branch and require exact-head re-validation.
