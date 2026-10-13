# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Notification Channels & Activity Center
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-NTF-001 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-NTF-001 - Authorized operator configures supported notification channel
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID; supported isolated notification channel and permitted actor
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Authorized operator configures supported notification channel
    And perform the scenario action using an approved browser or domain test client: Authorized operator configures supported notification channel
    And configure/validate instance and inspect delivery eligibility
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-001
    Then safe configuration status, validation/audit and correct delivery eligibility
    And channel readiness and audit reflect authoritative test response
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-NTF-002 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-NTF-002 - Delivery fails and retry/dedup encounters same event key
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID; deterministically failing delivery and one canonical event key
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Delivery fails and retry/dedup encounters same event key
    And perform the scenario action using an approved domain/service test client: Delivery fails and retry/dedup encounters same event key
    And retry/replay identical event key and inspect delivery history
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-002
    Then no false Delivered state, duplicate flooding or unbounded retry
    And bounded dedup avoids flooding and no false Delivered
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-NTF-003 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-NTF-003 - Channel disabled or unsupported provider is selected
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID; disabled channel and unsupported provider fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Channel disabled or unsupported provider is selected
    And perform the scenario action using an approved browser or domain test client: Channel disabled or unsupported provider is selected
    And attempt delivery for both and inspect selected transport
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-003
    Then send is blocked or correctly marked ineligible; no silent fallback
    And ineligible status recorded without silent fallback
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-NTF-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-NTF-004 - Notification Center tabs, filters, details and read-only activity links
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID; Notification Center fixtures with error/read/unread and multiple rows
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Notification Center tabs, filters, details and read-only activity links
    And perform the scenario action using an approved browser or domain test client: Notification Center tabs, filters, details and read-only activity links
    And change filters/Rows, open detail and clear filters
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-NTF-004
    Then correct pagination, accurate status, accessible interactive disclosure
    And event status and pagination remain accurate and accessible
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

