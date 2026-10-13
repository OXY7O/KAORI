# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# Reusable specification only: runtime outcomes and human decisions live in execution records.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Kubernetes — Analytics & Forecast
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-KAN-001 @positive @medium @ui @non_ui @draft
  Scenario: UAT-KAN-001 - Operator selects cluster/time range and opens utilization/capacity/forecast
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures
    When operator selects cluster/time range and opens utilization/capacity/forecast
    Then charts and summaries retain chosen scope, units, time window and source freshness

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KAN-002 @negative @high @ui @non_ui @draft
  Scenario: UAT-KAN-002 - Metrics source becomes unavailable or returns no data
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures
    When metrics source becomes unavailable or returns no data
    Then never display zero as measured utilization or unknown as Normal

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-KAN-003 @negative @high @non_ui @draft
  Scenario: UAT-KAN-003 - Invalid/out-of-scope metrics binding or scope is submitted
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures
    When invalid/out-of-scope metrics binding or scope is submitted
    Then no cross-cluster fallback or fabricated demand/capacity forecast

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-KAN-004 @positive @medium @ui @draft
  Scenario: UAT-KAN-004 - Charts, selectors and tables render under light/dark and narrow viewports
    Given committed multi-scope metrics/forecast evidence with fresh, stale and missing-data fixtures
    When charts, selectors and tables render under light/dark and narrow viewports
    Then labels/legends visible, no horizontal document overflow or clipped actions

