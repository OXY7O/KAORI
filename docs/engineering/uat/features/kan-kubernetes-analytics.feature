# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Kubernetes — Analytics & Forecast
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-KAN-001 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-KAN-001 - Operator selects cluster/time range and opens utilization/capacity/forecast
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; two cluster metric snapshots and two time windows
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator selects cluster/time range and opens utilization/capacity/forecast
    And perform the scenario action using an approved browser or domain test client: Operator selects cluster/time range and opens utilization/capacity/forecast
    And switch scope/window then inspect chart series, units and timestamps
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-001
    Then charts and summaries retain chosen scope, units, time window and source freshness
    And aggregates and forecasts retain exact source and selected scope
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KAN-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-KAN-002 - Metrics source becomes unavailable or returns no data
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; missing, stale and disconnected metrics provider fixtures
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Metrics source becomes unavailable or returns no data
    And perform the scenario action using an approved browser or domain test client: Metrics source becomes unavailable or returns no data
    And open chart/KPI for each failure and inspect tooltip readiness
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-002
    Then never display zero as measured utilization or unknown as Normal
    And unknown utilization is never plotted as observed zero/normal
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-KAN-003 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-KAN-003 - Invalid/out-of-scope metrics binding or scope is submitted
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; wrong-cluster or invalid metric source binding
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Invalid/out-of-scope metrics binding or scope is submitted
    And perform the scenario action using an approved domain/service test client: Invalid/out-of-scope metrics binding or scope is submitted
    And submit invalid analytics scope then inspect persisted output
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-003
    Then no cross-cluster fallback or fabricated demand/capacity forecast
    And cross-cluster substitution and fabricated forecast are rejected
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; source freshness, scope keys, rendered state and normalized read-back.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-KAN-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-KAN-004 - Charts, selectors and tables render under light/dark and narrow viewports
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures; deterministic charts in light/dark with six viewport sizes
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Charts, selectors and tables render under light/dark and narrow viewports
    And perform the scenario action using an approved browser or domain test client: Charts, selectors and tables render under light/dark and narrow viewports
    And interact with chart legend, tooltip and selector in each viewport
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-KAN-004
    Then labels/legends visible, no horizontal document overflow or clipped actions
    And no clipped labels, illegible contrast or document overflow
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

