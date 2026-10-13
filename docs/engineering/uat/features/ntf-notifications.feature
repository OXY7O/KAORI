# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# All scenarios: specification only, execution NOT RUN, human acceptance PENDING.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Notification Channels & Activity Center
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-NTF-001 @positive @medium @ui @non_ui @draft @not_run
  Scenario: UAT-NTF-001 - Authorized operator configures supported notification channel
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID
    When authorized operator configures supported notification channel
    Then safe configuration status, validation/audit and correct delivery eligibility

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-NTF-002 @negative @high @non_ui @draft @not_run
  Scenario: UAT-NTF-002 - Delivery fails and retry/dedup encounters same event key
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID
    When delivery fails and retry/dedup encounters same event key
    Then no false Delivered state, duplicate flooding or unbounded retry

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-NTF-003 @negative @high @ui @non_ui @draft @not_run
  Scenario: UAT-NTF-003 - Channel disabled or unsupported provider is selected
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID
    When channel disabled or unsupported provider is selected
    Then send is blocked or correctly marked ineligible; no silent fallback

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-NTF-004 @positive @medium @ui @draft @not_run
  Scenario: UAT-NTF-004 - Notification Center tabs, filters, details and read-only activity links
    Given controlled channel fixture; disabled/failed delivery, permissions and stable event ID
    When notification Center tabs, filters, details and read-only activity links
    Then correct pagination, accurate status, accessible interactive disclosure

