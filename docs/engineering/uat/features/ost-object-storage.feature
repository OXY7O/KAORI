# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Object Storage — Inventory & Analytics
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-OST-001 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-OST-001 - Operator views registered Object Storage systems and bucket inventory
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; two Object Storage systems with distinct committed bucket inventories
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator views registered Object Storage systems and bucket inventory
    And perform the scenario action using an approved browser or domain test client: Operator views registered Object Storage systems and bucket inventory
    And open bucket detail for selected system and inspect source age
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-001
    Then correct system identity, bucket scope, committed metrics and details
    And metrics and bucket rows do not mix systems
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-OST-002 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OST-002 - Object Storage provider is unreachable, disabled or returns partial results
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; previous storage snapshot plus provider outage/partial listing
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Object Storage provider is unreachable, disabled or returns partial results
    And perform the scenario action using an approved browser or domain test client: Object Storage provider is unreachable, disabled or returns partial results
    And reload inventory and readiness under disconnected source
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-002
    Then truthful unknown/stale/degraded presentation; no fabricated empty bucket list
    And uI is stale/partial/unknown instead of empty/healthy
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-OST-003 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OST-003 - Bucket registry search/filter/pagination and details interaction
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; bucket registry exceeding five rows with unmatched search
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Bucket registry search/filter/pagination and details interaction
    And perform the scenario action using an approved browser or domain test client: Bucket registry search/filter/pagination and details interaction
    And filter, change Rows, clear and open bucket detail on mobile
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-003
    Then five-row default, stable filters, accessible detail/modal and clear feedback
    And table defaults five and remains responsive/accessible
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; normalized source identity, committed record and provider read-back/adapter call ledger.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-OST-004 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-OST-004 - Forecast/usage receives mismatched source or missing data
    Given isolated S3-compatible fixture/MinIO sandbox or stored object snapshot and stale/unavailable cases; wrong system binding or missing usage evidence
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Forecast/usage receives mismatched source or missing data
    And perform the scenario action using an approved domain/service test client: Forecast/usage receives mismatched source or missing data
    And request forecast under invalid source then inspect normalized output
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OST-004
    Then no cross-system substitution, bogus zero capacity or unsupported trend claim
    And no cross-system substitution or bogus zero/trend
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

