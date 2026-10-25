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


  # Object Storage Inventory human-review coverage #3186; no new runner.

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-005 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OST-005 - Inventory Overview separates collection readiness from protection attention
    Given one registered MinIO X300 with current committed inventory and three buckets
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the operator opens the Inventory Overview
    Then the Hero and Inventory Data Snapshot show registered system and committed 1-of-1 coverage
    And Fleet Ready expresses collection readiness while Protection Attention still reports three assessed bucket findings
    And quota assessment, public exposure, collected usage and both asset catalog counts remain independently visible

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-006 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OST-006 - Systems table preserves provider identity, filters and committed freshness
    Given the committed MinIO X300 system belongs to Development and has a timestamped inventory snapshot
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the operator filters Systems by Ready and searches MinIO then clears the filters
    Then the system appears exactly once with provider, environment, release, endpoint and snapshot status
    And the shared table defaults to five rows and keeps scoped counts and filter state consistent
    And opening or filtering the table does not call a live provider or execute an inventory job

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-007 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OST-007 - System detail displays provider connection and snapshot evidence without mutation
    Given a selected system has recorded MinIO identity and committed connection and inventory metadata
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the operator opens Systems View Details then closes the Full Workspace Modal
    Then the detail identifies the system, provider connection, compatibility profile, and committed inventory snapshot
    And missing optional fields remain Not Reported rather than guessed
    And the header, evidence fields, modal close and keyboard focus are accessible without changing provider state

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-008 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OST-008 - Buckets overview and filters reconcile canonical asset counts
    Given the committed MinIO X300 snapshot includes buckets kaori reports and thanos
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the operator opens Buckets & Containers then filters to Development Bucket and searches kaori
    Then the unfiltered view shows three buckets and zero container-native assets
    And the filtered list and Assets in Scope posture both show one kaori bucket
    And Clear Filters restores all three identities and canonical five-row pagination

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-009 @positive @high @ui @specified @owner_review
  Scenario: UAT-OST-009 - Bucket detail adopts Kubernetes unified header and evidence-labelled sections
    Given the kaori MinIO bucket has a current committed snapshot and Protection Attention
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the operator opens kaori View Details and inspects the complete native detail
    Then the compact header separates bucket name and actual protection state from system provider and native type
    And Identity Snapshot Capacity Protection Lifecycle Provider and MinIO Configuration rails have evidence-bound labels
    And quota usage versioning encryption public exposure and provider-native settings remain truthful and never become invented compliance

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-010 @negative @high @ui @specified @owner_review
  Scenario: UAT-OST-010 - Partial bucket observations never become fabricated zeros or Healthy
    Given an isolated Object Storage fixture has missing or stale quota usage or protection evidence
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the operator views Inventory Overview and bucket detail under the partial fixture
    Then stale unavailable or unobserved evidence stays distinct from a genuinely observed zero
    And Quota Assessed differs from Quota Configured and Fleet Ready does not certify protection controls
    And no previous committed identity is lost and no bogus Healthy bucket state is shown

  # New human-review specification. Exact-ID pytest/Playwright execution NOT RUN.
  @UAT-OST-011 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-OST-011 - Inventory direct URLs enforce source and actor authorization
    Given an actor lacks Object Storage Inventory read permission and a permitted actor has read-only access
    And the exact candidate SHA actor source and committed evidence have been recorded
    When the restricted actor requests Systems Buckets and detail endpoints directly
    Then the server rejects unauthorized request before revealing any source or bucket identity
    And foreign provider credentials endpoints and other systems metadata are not exposed
    And denied or permitted reads never trigger provider writes or Inventory Sync
