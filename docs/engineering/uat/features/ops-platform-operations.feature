# KAORI — human-readable Gherkin acceptance specifications
# Authority: #1738 scenario catalog; #1725 defines the normative QA record contract.
# Mapping: docs/engineering/KAORI_UAT_TEST_MAPPING_AUDIT.md
# Reusable specification only: runtime outcomes and human decisions live in execution records.
# Gherkin tags are traceability labels, NOT pytest markers and NOT a Cucumber runner.
# Do not treat simulated fixtures as provider-authoritative UAT evidence.

Feature: Platform Operations — Overview, Jobs & Executions
  These scenarios describe observable KAORI acceptance expectations.
  Execution remains under existing pytest and Playwright capability-owned test suites.
  Human reviewers accept exact-candidate evidence separately.

  Background:
    Given the selected KAORI source candidate and approved capability contract have been reviewed
    And any test fixture or provider access is isolated and authorized

  # Scope: Both; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-OPS-001 @positive @medium @ui @non_ui @draft
  Scenario: UAT-OPS-001 - Operator views Jobs registry, selects failed execution and reads details
    Given known JobExecution history, policy scopes and isolated queue worker fixtures
    When operator views Jobs registry, selects failed execution and reads details
    Then correct job owner, state, error evidence and link to owning capability

  # Scope: Non-UI; risk: High; initial catalog wording — refine with capability owner.
  @UAT-OPS-002 @negative @high @non_ui @draft
  Scenario: UAT-OPS-002 - Job retry/cancel occurs during worker result race
    Given known JobExecution history, policy scopes and isolated queue worker fixtures
    When job retry/cancel occurs during worker result race
    Then no duplicate forbidden execution or false terminal status

  # Scope: Both; risk: High; initial catalog wording — refine with capability owner.
  @UAT-OPS-003 @negative @high @ui @non_ui @draft
  Scenario: UAT-OPS-003 - Worker/queue dependency unavailable or blocked
    Given known JobExecution history, policy scopes and isolated queue worker fixtures
    When worker/queue dependency unavailable or blocked
    Then correct blocked/degraded visibility, no invented execution success

  # Scope: UI; risk: Medium; initial catalog wording — refine with capability owner.
  @UAT-OPS-004 @positive @medium @ui @draft
  Scenario: UAT-OPS-004 - Platform Overview and Jobs tabs/filters/actions are exercised
    Given known JobExecution history, policy scopes and isolated queue worker fixtures
    When platform Overview and Jobs tabs/filters/actions are exercised
    Then committed-only summary, appropriate permission scopes and canonical visual states

