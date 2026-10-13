# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Object Storage — Inventory & Analytics
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-OST-001 @positive @medium @ui @non_ui @draft @not_run
  Scenario: UAT-OST-001 - Operator views registered Object Storage systems and bucket inventory
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases
    When operator views registered Object Storage systems and bucket inventory
    Then correct system identity, bucket scope, committed metrics and details

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-OST-002 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-OST-002 - Object Storage provider is unreachable, disabled or returns partial results
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases
    When object Storage provider is unreachable, disabled or returns partial results
    Then truthful unknown/stale/degraded presentation; no fabricated empty bucket list

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-OST-003 @positive @medium @ui @draft @not_run
  Scenario: UAT-OST-003 - Bucket registry search/filter/pagination and details interaction
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases
    When bucket registry search/filter/pagination and details interaction
    Then five-row default, stable filters, accessible detail/modal and clear feedback

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-OST-004 @negative @high @non_ui @draft @not_run
  Scenario: UAT-OST-004 - Forecast/usage receives mismatched source or missing data
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases
    When forecast/usage receives mismatched source or missing data
    Then no cross-system substitution, bogus zero capacity or unsupported trend claim

