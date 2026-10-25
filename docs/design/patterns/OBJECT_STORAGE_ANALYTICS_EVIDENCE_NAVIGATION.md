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
| Capacity & Usage | Committed snapshot source/status banner | `Summary` → expandable Inventory & Operational Reconciliation; `Quota & Buckets` owns quota/usage field evidence |
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

Validate one central tab; five domains without duplicate Evidence tabs; context status/source and link with `system_id`, `time_range`, `tab=evidence`; Capacity reconciliation disclosure; Forecast worker metadata; Alerts fallback detail; missing/partial states. Validate 6h and 24h, narrow/desktop and light/dark, keyboard/hover, real HTTP 200, and source formatting/pytest. This document does not equate static contract success with completed browser UAT.

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
    When I expand "Inventory & Operational Reconciliation"
    Then committed Inventory and operational comparison are available
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
