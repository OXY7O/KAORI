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
| Alerts & Anomalies | Alertmanager-first resolved source/status in context | `Alert Overview` → compact native `View Alert Source` dialog; `Anomaly Signals` → committed KAORI boundary evaluation table, independent of provider alerts |

## Semantic and security guardrails

- Provider/source stays authoritative; KAORI normalizes and reads **committed** evidence.
- Unknown, Not Configured, No Current Samples, Metric Not Scraped, Runtime Query Failed, unavailable worker materialization and stale states must never become fabricated zeros or healthy postures.
- Metrics Source `ALERTS` is narrower than Alertmanager lifecycle; preserve the original source-reconciliation semantics.
- RBAC remains `object_storage_analytics.view`; no new routes, permissions, workers, models or schema.
- Existing legacy shared Evidence partials remain in repository for other consumers; they are no longer duplicated in the five workspaces. Cross-domain adoption requires separate design review.

## UAT acceptance

Validate one central tab; five domains without duplicate Evidence tabs; context status/source and link with `system_id`, `time_range`, `tab=evidence`; Capacity Reconciliation modal; Forecast worker metadata; Alerts fallback detail; missing/partial states. Validate 6h and 24h, narrow/desktop and light/dark, keyboard/hover, real HTTP 200, and source formatting/pytest. This document does not equate static contract success with completed browser UAT.

Workstream delivery: issue #3260 → branch/commit → review PR to temporary `kaori/review/staging-uat` → operator UAT/acceptance. Official CI/CD, Full Admission, promotion and release remain on HOLD pending explicit user approval.

## Gherkin — Object Storage Analytics UAT acceptance scenarios

The operator accepted the reviewed Object Storage UI as satisfactory on **26 October 2026**, subject to later findings. This confirms the **visual review checkpoint**, not an executable step-by-step replay of every scenario below. Preserve separate gate evidence for each run, including exact branch/commit, viewport, selected system/window, source state, observed result, HTTP status, and pass/fail. Unexecuted scenarios remain **Pending**, not PASS.

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
    When I open the "View Alert Source" dialog
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

  Scenario: Overview shows the committed operational health and evidence authorities
    Given I have selected an Object Storage system with committed Inventory and Analytics snapshots
    When I open Analytics Overview and select "Data & Evidence"
    Then I see Metrics Source, Inventory, Alertmanager, and other applicable committed authorities
    And I can inspect source readiness and fallback without issuing a live provider read
    And Reconciliation shows Operational, Inventory, Drift, and evidence-based Assessment
    And source-specific Unknown or Stale states are not displayed as Healthy

  Scenario: Capacity physical headroom and quota governance remain separate
    Given committed capacity, usage, quota and trend evidence are available
    When I open Capacity & Usage and select "Summary"
    Then capacity utilization and physical remaining headroom retain their committed metric sources
    And bucket quota governance does not represent additional physical free capacity
    And usage direction describes observed history rather than guaranteed exhaustion

  Scenario: Capacity reconciliation uses the shared accessible dialog
    Given I am in Capacity & Usage with a selected system and time range
    When I activate "View Reconciliation" next to "View Data & Evidence"
    Then the native modal presents the committed Operational versus Inventory comparison
    And Drift retains the recorded Delta and Variance
    When I close the modal with Escape or the Close control
    Then focus returns to the invoking action
    And the selected system and window are unchanged

  Scenario: Capacity bucket filters are isolated from physical capacity calculations
    Given I open "Quota & Buckets" with committed bucket records
    When I filter by Bucket, Quota State and Quota Pressure
    Then the table and result count reflect the combined filters
    And a known Not Configured quota is not interpreted as Unknown
    And the physical headroom and usage metrics remain unchanged
    When I activate "Clear Filters"
    Then the table returns to the full bucket set with the selected system, window and Rows preserved

  Scenario: Performance preserves request reliability and source-qualified bucket evidence
    Given committed Request Rate, Error Rate and traffic evidence have been materialized
    When I open Performance and select "Request Health" or "Traffic & Trend"
    Then success/error ratios, queues and traffic are presented as distinct operating questions
    And "Request & Error Trend" has the canonical KAORI Guide
    When I open "Bucket Activity" and filter Usage Context or Bucket name
    Then request and error metrics never fall back to Inventory
    And missing metric samples remain Unknown rather than a fabricated 0.0

  Scenario: Forecast watch filters update records without removing the chart
    Given a committed Forecast Worker result and bucket forecast history are available
    When I open Forecast and select "Bucket Forecasts"
    Then "Bucket Forecast Records" displays the KAORI Guide
    And the current-versus-30-day projected usage chart is visible
    When I choose Forecast Watch "Baseline" and History Evidence "No History"
    Then only the forecast records are filtered and the chart remains visible
    And "Clear Filters" restores records while preserving system, history window and Rows
    And the forecast remains a planning signal, not an active provider alert

  Scenario: Forecast readiness and unavailable materialization remain source-specific
    Given the Forecast Worker has stale, insufficient, or unavailable evidence
    When I open "Forecast Outlook" or "Worker & Method"
    Then the worker generation status, history and selected method remain explicit
    And insufficient history does not become a zero-growth projection or Healthy state
    And opening the page does not require a live provider query

  Scenario: Top Consumers keeps metric provenance across storage and request rankings
    Given multiple committed buckets have usage, object, quota and request evidence
    When I open Top Consumers and compare "Storage Leaders" with "Request Activity"
    Then storage concentration and request/error activity are presented separately
    And each metric retains its supported Metrics Source or Inventory provenance
    And explicit "Not Configured" quotas are not interpreted as source collection failures

  Scenario: Consumer Records combines filters without fabricating missing values
    Given a bucket has observed request rate 0.0 and another has no request samples
    When I select "Consumer Records" and filter Request Evidence "Available"
    Then the bucket with request rate 0.0 remains included
    And the bucket without request samples is excluded
    When I select "Unavailable"
    Then only buckets with unavailable request evidence match that filter
    And Clear Filters preserves the selected Object Storage system, time range, tab and Rows

  Scenario: Provider Alerts and alert-source lifecycle remain independent of KAORI anomaly evaluation
    Given Alertmanager lifecycle evidence and KAORI operating metrics are committed
    When I open Alerts & Anomalies and select "Provider Alerts"
    Then provider alerts retain Alertmanager status, receiver, silence and inhibition authority
    When I activate "View Alert Source"
    Then a compact accessible dialog shows Selected Policy, Resolved Alert Source and Consumer
    And Metrics Source ALERTS fallback is identified as rule-state-only evidence
    And KAORI anomaly evaluations are not presented as provider firing alerts

  Scenario: Anomaly Signals explains all four operating boundaries
    Given the committed request error ratio is 62.5 percent
    And committed capacity, waiting-request and node metrics are independently available or unavailable
    When I select "Anomaly Signals" in Alerts & Anomalies
    Then I see exactly four boundary evaluation rows
    And the rows are Capacity Utilization, Request Error Ratio, Waiting Requests, and Offline Storage Nodes
    And Request Error Ratio shows "62.5%" with severity "Critical"
    And its warning boundary is 5 percent and its critical boundary is 10 percent
    And any other boundary with missing evidence shows "Unavailable" and "Unknown"
    And the Guide identifies this as deterministic KAORI evaluation, not advanced Intelligence correlation
    And the evaluation does not claim root-cause diagnosis

  Scenario Outline: Anomaly boundary thresholds retain their approved inclusive or strict limits
    Given a committed "<boundary>" observation of <observed>
    When KAORI evaluates its current operating boundary
    Then the boundary severity is "<severity>"
    And an observed zero remains a valid observation rather than missing evidence

    Examples:
      | boundary            | observed | severity |
      | Capacity Utilization| 84.9     | Normal   |
      | Capacity Utilization| 85.0     | Warning  |
      | Capacity Utilization| 95.0     | Critical |
      | Request Error Ratio | 4.9      | Normal   |
      | Request Error Ratio | 5.0      | Warning  |
      | Request Error Ratio | 10.0     | Critical |
      | Waiting Requests    | 0        | Normal   |
      | Waiting Requests    | 1        | Warning  |
      | Offline Storage Nodes | 0      | Normal   |
      | Offline Storage Nodes | 1      | Critical |

  Scenario: Missing anomaly evidence remains Unknown independently
    Given only one of the four boundary metrics has a committed observation
    When I select "Anomaly Signals"
    Then that boundary uses its observed value and applicable severity
    And each of the other three boundaries shows "Unknown" and "Unavailable"
    And Alert Overview anomaly counts continue to describe triggered findings only

  Scenario: Read-only Recommendations never substitute for external alert execution
    Given committed Analytics evidence is available for Capacity, Performance, Forecast, Top Consumers or Alerts
    When I open the corresponding "Recommendations" tab
    Then any recommendations remain source-qualified read-only review guidance
    And missing or stale evidence cannot produce a fabricated safe posture
    And no action is executed against Alertmanager or the Object Storage provider

  Scenario: Visual consistency and keyboard behavior across Object Storage workspaces
    Given I use a desktop viewport of 1440 by 900 or a mobile viewport of 390 by 844
    And I select light mode or dark mode
    When I navigate Overview, Capacity, Performance, Forecast, Top Consumers and Alerts
    Then canonical Violet Guides are accessible by focus, pointer and touch
    And table filters, loading, empty states and pagination preserve their existing shared patterns
    And long tables scroll horizontally on narrow screens without losing data
    And dialogs support Escape, Close and focus restoration
    And the browser reports no unexpected Jinja or HTMX HTTP errors
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

## 26 October 2026 — Capacity workspace contextual Guides (#3295)

- The **Capacity & Usage Workspace** heading owns a title-adjacent canonical KAORI Guide explaining the four tabs and their committed-evidence boundary. It does not duplicate the Overview Data & Evidence tab or introduce provider live queries.
- The shared `_recommendations_workspace.html` displays a Capacity-only title-adjacent Guide for evidence-derived priority, review navigation, and missing/stale evidence; recommendation actions, cards, paging, and other domains remain unchanged.
- **Analytics Controls & Data Readiness** reuses the existing `_controls_readiness.frame` macro with an optional `title_accessory`. Only Capacity passes a canonical Guide; other consumers continue rendering the original h2 with no layout changes. The Guide distinguishes selector scope, collection-time Metrics Source readiness, and the committed worker-materialized Analytics Snapshot.
- The previously reported `djlint` wrap on the Capacity-only Bucket Records header icon is corrected without modifying the icon or table behavior.
- UAT: verify all three anchored Guides at desktop 1440×900 and mobile 390×844, light/dark, hover/click/keyboard/touch and popover clipping; confirm changing system/window and switching content tabs still works. Source-readback is not a substitute for exact-head `djlint`, Jinja, pytest, or human visual acceptance.

## 26 October 2026 — Performance Analytics UAT polish (#3301)

- The canonical `components/info_tip.html` title-level `variant='guide'` (**visible Violet Guide control, never standalone '?'**) appears next to Performance Analysis Workspace, Request Path Operating Boundary, Throughput & Request Direction, and Performance Bucket Request Path Records.
- Analytics Controls & Data Readiness owns a single per-page Guide on **all Object Storage Analytics pages** (including Overview, Capacity, Performance, Top Consumers, Forecast and Alerts). The existing shared frame's optional `title_accessory` remains backward compatible. Its Guide explicitly separates source/selector context from worker-committed snapshot freshness, forecast-worker status and provider alert lifecycle.
- Shared Recommendations displays the standard context-derived Guide on each of the five owning workspaces, never on Overview. A recommendation is review guidance rather than provider mutation, regardless of whether guidance cards are empty.
- Request Health explanation copy is shortened without changing error ratios, 5% review / 10% critical thresholds, missing-evidence status or pressure logic. Throughput & Request Direction's Highest Request Demand/Error Ratio callout summaries retain their observed dynamic value and coverage but use concise text to fit one line on desktop.
- Performance Bucket Request Path Records reuses the shared header icon surface, title Guide, right-aligned Clear Filters action, responsive table, and canonical table select styling. **Usage Context** filters committed per-bucket `usage_bytes`/`usage_source` as Metrics Source, Committed Inventory, or Unavailable; it never manufactures request/error metrics from Inventory. Search and Usage Context combine, default pagination remains five, and system/window/tab/Rows survive HTMX navigation and Clear Filters. The filter is scoped only to Performance.
- Update prior textual contracts to the new approved concise copy while preserving source-bound guards. UAT: browser GET and keyboard/pointer/touch Guide behavior, narrow/desktop, light/dark, no clipping; filter each provenance category and no-results, Clear Filters, 12h/6h and pagination; request/error Unknown must never become numeric zero. Full Admission and release remain HOLD pending Dev Container tests and Human Acceptance.

## 26 October 2026 — Analysis workspace section hierarchy UAT (#3313)

- After **Analytics Controls & Data Readiness** and any committed refresh notice, display a single standalone title and concise description before each owning Object Storage Analytics workspace: Capacity & Usage Analysis, Performance Analysis, Forecast Analysis, Top Consumers Analysis, and Alerts & Anomalies Analysis.
- Reuse the exact existing **Overview** section heading primitives from `analytics/index.html`: `space-y-1` container, `text-base font-semibold text-content-primary` h2 and `text-sm leading-6 text-content-secondary` description. The page-level introduction is distinct from (and does not replace) the inner Workspace card title.
- The shared composition uses a page-key guarded map for the five non-Overview domains, avoiding five duplicated blocks or a new component. Overview retains its existing **Operational Posture** and **Analysis Workspaces** headings without duplicates. Do not alter the provider/worker authority, snapshot status, charts, tabs, navigation, accessibility or metric semantics.
- UAT: inspect desktop and mobile for each of five pages, light/dark, both current and stale snapshots; verify placement directly below Controls and above the workspace card, correct visible heading and short copy, no unintended blank band, no Jinja/HTTP 500 and no Overview regressions. Focused contract checks Jinja parse, per-domain coverage, guard and heading order. Official Full Admission, staging/main promotion and release remain HOLD.

## 26 October 2026 — Forecast Outlook, Usage Trend, bucket watch and worker UAT (#3315)

- **Forecast Operating Boundary**, **Storage Usage Forecast**, **Bucket Forecast Watch**, and **Forecast Worker Refresh** use title-adjacent canonical KAORI Violet `Guide` from `components/info_tip.html` (`variant='guide'`, not bare question-mark glyphs). Explain historical data versus worker projection, forecast readiness, quota timing, and worker authority.
- Storage Usage Forecast reuses **Overview Capacity's** compact trend composition: three semantic icon/status signal cells **above** the chart, responsive three-column grid and shorter 260/280px chart. Observed history remains solid and the worker's 30-day projection dashed; both Forecast Outlook and Usage Trend preserve existing chart attributes and committed data. Separate per-tab `object_storage_trend_instance` values yield unique Info Tip DOM IDs for their simultaneously rendered Forecast panels.
- Remove only the redundant bottom `Operational Reading` callout in Forecast Outlook. Keep its four KPI values, forecast posture status badge, worker materialization authority, and missing-evidence behavior.
- **Bucket Forecast Watch** owns the summary and current-versus-projected chart. **Bucket Forecast Records** is a separate KAORI table surface following the Watch card, with its original HTMX target/indicator, Search/Watch/History filters, Clear Filters, pagination and empty state. Its description becomes one concise desktop line and wraps at narrow widths. The table remains independent of the chart's watch-state controls and retains source evidence.
- Follow the exact `djlint` one-line `analysis_intros` map and `ruff format` long-tuple style from UAT logs, without editing the approved copy or creating new templates/components. Contract tests check Jinja parse, Guides, distinct instances, three metrics, separated cards, preserved chart/data hooks, and exclusion of the redundant callout.
- Human UAT: light/dark desktop 1440×900 and mobile 390×844; hover, focus and touch Guides; both Forecast chart appearances; chart and records are distinct; active/empty/partial history cases; filtering and HTMX paging; no HTTP 500; worker status is not interpreted as provider health. Full admission and release stay HOLD.

## 26 October 2026 — Forecast chart lifecycle and Clear Filters regression (#3322)

- The standalone `_bucket_forecast_table.html` now explicitly imports `analytics/components/_analysis_surfaces.html` before calling `analysis_surface.evidence_shell_classes()`. The GET route renders this partial directly; relying on `analytics/index.html` to supply its macro can cause a Jinja UndefinedError/HTTP 500 on filtered HTMX requests, leaving stale table rows and no server-side Clear Filters update.
- After #3315 detached **Bucket Forecast Records** from the **Bucket Forecast Watch** chart, its HTMX filter and pagination calls update only `#object-storage-bucket-forecast-table-panel`. Global chart teardown on every `htmx:beforeSwap` was incorrect: it destroyed unrelated visible/hidden chart canvases even when no chart DOM was replaced. The Object Storage Analytics chart controller now checks the actual swap target before destroying Chart.js instances, and scopes re-rendering to chart panels inside the swapped target or the newly visible tab. A table-only swap never destroys/recreates sibling forecast chart data or appearance.
- Canonical `registry_ui.clear_filters_action` remains right-aligned in the table header and clears Search, Forecast Watch, and History Evidence while retaining selected system, 30D/7D/90D history and Rows. Server-derived filter-state remains authoritative after successful HTMX response; a small local form-state sync exposes the same action immediately on interactive filter changes so an unavailable or delayed HTMX response does not strand the user without a reset link. No change to the existing table filter predicates, recorded metrics, worker authority, chart dataset, or query semantics.
- A dedicated regression checks scoped JS lifecycle, independently rendered chart/table markup, clear action presence/visibility state, and four filter view cases (intersection, no result, invalid state, clear). Format-only UAT findings in Forecast Guide `djlint` and workspace contract `ruff format` were addressed.
- Human UAT: choose Forecast Watch=Baseline and History Evidence=No History, confirm chart remains visible and unchanged, Clear Filters appears right in header, filtered row count matches criteria, and clicking it restores all records while preserving Rows/history. Exercise search, no results, pagination, multiple tabs and windows, light/dark/mobile and browser error console. Retest exact merge SHA; static read-back is not QA. Official admission, staging/main and release HOLD.

## 26 October 2026 — Top Consumers KAORI Guides and source-qualified record filters (#3330)

- **Storage Consumer Leaders**, **Request Activity Leaders**, and **Consumer Records** use the canonical title-adjacent Violet `Guide` from `components/info_tip.html` with `variant='guide'` (never a standalone question-mark tooltip). The guides distinguish storage/object concentration, request/error reliability and each field's source authority.
- **Consumer Records** reuses the shared KAORI responsive table header icon, compact result badge, right-aligned `registry_ui.clear_filters_action`, HTMX form, search/select filter styling, default five-row pagination and empty/loading states. Filter controls are **Search Bucket**, **Usage Context** (Metrics Source / Committed Inventory / Unavailable), **Quota State** (Configured / Not Configured / Unknown), **Quota Pressure** (Within / 85–<95% / ≥95%), and **Request Evidence** (Available / Unavailable).
- Predicates are composed server-side over **already committed per-bucket rows**, with no new live provider request, inference or recomputation. Usage Context and quota selectors reuse the existing Performance/Capacity boundaries while becoming available on Top Consumers. Request Evidence checks `request_rate is not None`; an explicitly observed zero request rate counts as **Available**, and unavailable samples never become zero. Quota pressure applies only to known, configured quotas and known utilization.
- All local filters combine with search. Clear Filters removes their query parameters while preserving system, time window, tab=records and Rows. Pagination carries all active filters and uses 5/10/25/50 rows. Other workspaces retain their own controls and are not affected by Request Evidence.
- UAT: 1440×900 and mobile, light/dark, Guides hover/focus/click, filter combinations, search, no-results, Clear Filters, rows/page/pagination and HTMX 200. Verify zero-rate vs unknown request evidence, unconfigured vs unknown quota, and matching result count. Formatter findings from prior Forecast UAT were fixed in the same scoped work; executable QA and Human Acceptance are still required. Official admission and release stay HOLD.

## 26 October 2026 — Alerts overview Guide and provider lifecycle native dialog (#3336)

- **Provider Alert & Anomaly Overview** displays the canonical KAORI Violet `Guide` (`components/info_tip.html`, `variant='guide'`) adjacent to its heading, not an unlabeled question-mark icon. Its guidance distinguishes the resolved Alertmanager-first provider stream, Metrics Source ALERTS rule-state-only fallback, and independent KAORI metric-derived anomaly signals; a current zero does not prove overall system health and absent evidence remains Unknown.
- Replace the prior inline **Alert Source & Lifecycle Details** expandable section with the same **native KAORI dialog** already used by Capacity → View Reconciliation. The Alerts-only **View Alert Source** action sits beside **View Data & Evidence** in the shared **Committed Evidence** bar. The dialog uses the existing `data-kaori-dialog-open/close`, `data-kaori-native-dialog`, `kaori-native-dialog`, accessible title/description, responsive `max-w-5xl` scroll region, header/footer and keyboard/native close lifecycle; it adds no new client-side controller or provider mutation.
- The dialog renders `_alerts_source_evidence.html` exactly once, in an embedded form without a duplicate nested header. Preserve Selected Policy, Resolved Alert Source, Alertmanager Consumer, Alertmanager Authority, Metrics Source Fallback, source/capability distinctions, and all committed lifecycle details. Other Alerts tabs and the Overview central audit link remain unchanged.
- Previous Top Consumers (#3330) UAT log showed two failing assertions because August filter-isolation tests still assumed Top Consumers ignored quota/usage filters that are now intentionally available. Tests now verify Top Consumers does filter, while unrelated Capacity/Performance contexts do not inherit those selectors; formatter findings on Request Activity Guide, `bucket_table.py`, and its filter unit tests are normalized. Do not interpret those prior failures as provider/runtime regressions without contrary evidence.
- Human UAT: Alerts Overview Guide hover/focus/click, View Alert Source click/Escape/Close, focus returns to trigger, no duplicate source blocks or scroll clipping at 1440×900 and mobile, light/dark, no HTTP/Jinja error; verify Alertmanager and Metrics Source fallback keep their evidence boundaries. Also rerun amended Top Consumers tests. Keep issue open pending real executable checks and Human Acceptance; official admission and promotion HOLD.

## 26 October 2026 — Alerts record header and source lifecycle modal visual refinement (#3343)

- The **Provider Alert Records** table header now reuses `table_ui.block_icon_classes()` with the `bell-ring` icon, matching KAORI Capacity/Consumer/Forecast record headers; its short desktop single-line helper remains responsive on narrow screens. The helper distinguishes Alertmanager lifecycle metadata from Metrics Source ALERTS rule states without changing the provider/source authority.
- **View Alert Source** retains the already-admitted *pattern* (not an official gate pass) of the Capacity **View Reconciliation** native dialog: same open/close/ARIA semantics, modal shell, scroll-safe content, and read-only footer. Its inner content now has two clearly separated groups instead of a pasted snapshot: **Source Resolution** (Selected Policy, Resolved Alert Source and Alertmanager Consumer, with source-bound semantic status labels) and **Lifecycle Capability Boundaries** (Alertmanager lifecycle-rich authority versus Metrics Source narrower rule-state-only fallback). Use KAORI Violet/neutral icon roles, responsive three-/two-column cards, shared surface/border tokens, concise captions, and preserve source/fallback semantics and evidence.
- The old alert source evidence `interpretation_callout` grid is not reused inside this redesigned modal; the same authority statements remain verbatim in titled cards. No new provider calls, mutation, or independent alert lifecycle state. The page/tab controls and existing modal trigger stay unchanged.
- Repaired previous UAT regressions: `bucket_quota_state=critical` is invalid and normalizes to `all` while the simultaneously selected `bucket_quota_pressure=critical` remains applicable to Top Consumers; asserted via both view state and query params. Shared action class counts are now asserted in the scoped **Capacity** branch rather than incorrectly assuming the source template contains only Capacity and common link actions (it also contains the approved Alerts modal action). Also normalized the previously reported Alerts workspace/source `djlint` findings. Updated the old concise-copy contract to retain the fallback boundary through the source evidence partial.
- UAT: run `djlint`, Ruff and focused contracts at the exact merged holding SHA; visually test 1440×900/mobile, light/dark, badge/status spacing, source resolution fallback, modal scroll and keyboard Escape/Close/focus return, records header layout, table search/filter/paging and no unknown→zero conversion. Issue remains OPEN through human acceptance; official Full Admission, staging/main and release remain HOLD.

## 26 October 2026 — Compact informational Alert Source modal UAT (#3348)

- Human visual review rejected the oversized dashboard-like five-card Alert Source body introduced in #3343. **The approved direction for View Alert Source is a compact KAORI informational dialog**, not a second analytics workspace or dashboard.
- Retain the same native KAORI dialog/trigger/ARIA/Escape/Close lifecycle and committed provider authority, but reduce the modal to `max-w-2xl`, a neutral `bg-surface-card` body and standard restrained spacing. The body contains **one** divided definition list with Selected Policy, Resolved Alert Source + semantic status, and Alertmanager Consumer + status. Use a responsive label/value row pattern rather than three cards and icon tiles.
- Below the list, a small **Evidence Coverage** note explains (1) Alertmanager's receiver/silence/inhibition and lifecycle authority and (2) Metrics Source ALERTS rule-state fallback without routing, receiver, silence or inhibition lifecycle metadata. No duplicate headings, decorative cards, or repeated hero. Unavailable source/state remains source-owned, never converted to healthy or zero.
- The concise **Provider Alert Records** desktop helper from #3343 remains in place. Two August contracts that still expected the old long wording were updated to the approved short wording without deleting coverage. `djlint` formatting findings from #3343 and Ruff quote-style findings in the dedicated evidence contract were addressed in the new compact partial/test.
- UAT: verify light/dark at 1440×900 and mobile widths, neutral compact hierarchy, long consumer value wrapping, resolved/unknown fallback badge, single included evidence body, tab navigation and native ESC/X/footer Close focus restoration. Run djlint/Ruff/focused pytest on exact holding-branch SHA. Issue OPEN pending Human Acceptance; official admission, staging/main and release HOLD.

## 26 October 2026 — Performance/Forecast Guides and compact Top Consumers evidence (#3354)

- **Request & Error Trend** on Performance renders a title-adjacent canonical Violet `Guide` (`components/info_tip.html`, `variant='guide'`, `placement='right'`) in the `trend_mode == 'performance'` branch. The Guide differentiates committed request/error rates and evidence gaps, does not confuse trend direction with request latency or root cause, and never fills missing request metrics from Inventory. Existing Overview, Capacity and Forecast trend Guide identifiers remain unaffected.
- **Bucket Forecast Records** retains its independent HTMX-rendered KAORI table surface, filters, Clear Filters, pagination and history/system selection. Its heading now includes a canonical, unique Guide explaining forecast-ready history, worker quota/watch planning signals and the boundary from active provider alert lifecycle. The Guide macro is imported directly in the table partial so direct HTMX rendering does not inherit a missing macro from a parent.
- **Top Consumers** uses concise single-line desktop evidence helpers without changing calculations: `Quota Evidence` still displays the three committed dynamic counts (observed quota states, known bucket total, explicit Not Configured state); `Reliability Boundary` states that error ratio helps triage rather than establish root cause, and directs follow-up to Performance. At narrow widths, text may wrap for accessibility; numeric meaning and unknown/not-configured distinctions remain unchanged.
- QA: check unique native Guides/keyboard focus, desktop 1440×900, mobile/light/dark, HTMX partial/empty-state, accurate quota counts and no regression to chart or alert semantics. Run existing `djlint`, Ruff and focused pytest; no custom validation script. Official Full Admission, staging/main promotion and release remain HOLD until Human Acceptance.

## 26 October 2026 — Complete four-boundary Anomaly Signal evaluation (#3360)

- **Authority:** Existing Object Storage Analytics `metric_risk_signals()` remains the triggered-findings contract used by `Alert Overview` counts and read-only `Recommendations`. Its outputs are **not** a complete inventory of all checks, hence the earlier Anomaly Signals tab displayed only one Critical row for a high request-error ratio. That is correct as a finding but too sparse as an operator evaluation view.
- **Anomaly Signals** now shows four committed KAORI metric boundaries on a standard, accessible, responsive `table_primitives.html` table, each including Operating Boundary, Observed, Threshold, Severity, and Evaluation. The header uses the existing Violet `Guide` from `components/info_tip.html` with `variant='guide'`, not an isolated question-mark tooltip.
- **Exact rules are unchanged:** Capacity Warning ≥85% / Critical ≥95%; Request Error Ratio Warning ≥5% / Critical ≥10%; Waiting Requests Warning strictly >0 (no Critical boundary); Offline Nodes Critical strictly >0 (no Warning boundary). Values are derived from existing source-qualified `utilization`, `error_ratio`, `waiting`, and `offline_nodes` only. A measured zero is Normal; each missing metric is individually **Unknown**, even when another boundary is Critical. No made-up data, no ML, no additional provider query.
- The new `metric_boundary_evaluations()` builder is evaluated **only over already loaded worker-committed Object Storage Analytics metrics in `_apply_alert_snapshot_context`**, not during fresh provider access. It supports historical committed snapshots without requiring a worker backfill, schema change, provider adapter, or altering the serialized snapshot. The existing alert and anomaly source authority, materialized-worker read boundary, and critical/warning findings rollup are preserved.
- **Architecture taxonomy:** Provider Alerts = authoritative Alertmanager lifecycle (or narrower Metrics Source ALERTS rule-state fallback). KAORI Anomaly Signals = deterministic domain-specific operating-boundary evaluations. Cross-domain intelligent correlation and diagnostic recommendations are separate, future capabilities; this view does **not** claim root cause, predictive anomaly detection, or an auto-created external alert.
- Human UAT: test four rows/threshold edges, normal vs missing evidence, separately Unknown boundaries, existing Overview anomalous count and Recommendations unchanged, Jinja table/Guide keyboard/focus, horizontal overflow on mobile, Violet/light/dark at 1440×900; use existing Ruff, djlint and pytest gates. This workstream remains on temporary `kaori/review/staging-uat` pending explicit acceptance; Full Admission, staging/main and release/tag HOLD.


## 26 October 2026 — Operator Object Storage UAT acceptance checkpoint (#3364)

- **Human feedback:** Object Storage UI across reviewed workspaces is **OK for the current UAT scope**. This is a visual/user acceptance checkpoint, not a blanket statement that all executable quality gates, environment permutations, security validation, or Gherkin cases have passed. Later issues/reviews remain permitted and must be tracked via new or existing scoped issues.
- **Last executable evidence before formatting-only follow-up:** operator reported `87 passed` in `13.10s` across the focused Analytics, alert-evidence and evidence-navigation tests. `ruff check` PASS; `djlint` identified formatting in `_alerts_signal_records.html` and `ruff format` identified an extra line break before `metric_boundary_evaluations`. These exact two findings are addressed under #3364, but **must be rechecked on the eventual merge SHA**. Do not claim formatter PASS until rerun.
- The above consolidated **Gherkin scenarios are acceptance specifications, not evidence that every step has been executed**. Record exact commit, environment, selected system/time window, scenarios, screenshot/HTTP/check output, pass/fail and human sign-off in issue comments or the existing UAT evidence workflow. Preserve source ownership: provider alerts originate in Alertmanager, KAORI anomaly boundaries are committed deterministic evaluations, and cross-domain Intelligence is separate.
- **Governance:** Temporary `kaori/review/staging-uat` only; official Full Admission, promotion PR to `kaori/staging`/main, deployment/release and tag stay **HOLD** until explicitly authorized. Project KAORI metadata and child issue #3364 relation should be reconciled before closure.
