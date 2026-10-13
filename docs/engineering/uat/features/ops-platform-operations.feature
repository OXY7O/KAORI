# KAORI UAT — readable Gherkin acceptance specifications
# Authority: #1738 catalog; #1725 QA evidence contract.
# Gherkin is a specification; existing pytest/Playwright executes tests, not Cucumber.
# Execution and human acceptance are recorded separately against an exact candidate.

Feature: Platform Operations — Overview, Jobs & Executions
  Scenario steps below are pending owner verification against the admitted implementation.
  Successful syntax review cannot substitute for a real test run.

  Background:
    Given an approved KAORI source candidate and capability contract have been selected
    And fixtures and any provider access have been explicitly authorized and isolated

  # Layer: Both; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-OPS-001 @positive @medium @ui @non_ui @specified @owner_review
  Scenario: UAT-OPS-001 - Operator views Jobs registry, selects failed execution and reads details
    Given known JobExecution history, policy scopes and isolated queue worker fixtures; failed JobExecution with known owner and error correlation
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Operator views Jobs registry, selects failed execution and reads details
    And perform the scenario action using an approved browser or domain test client: Operator views Jobs registry, selects failed execution and reads details
    And filter Jobs by failure and navigate to owning capability
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-001
    Then correct job owner, state, error evidence and link to owning capability
    And job state, owner and error evidence remain consistent
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

  # Layer: Non-UI; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-OPS-002 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-OPS-002 - Job retry/cancel occurs during worker result race
    Given known JobExecution history, policy scopes and isolated queue worker fixtures; in-flight job and concurrent cancellation/retry fixture
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Job retry/cancel occurs during worker result race
    And perform the scenario action using an approved domain/service test client: Job retry/cancel occurs during worker result race
    And race terminal worker result with cancel/retry action
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-002
    Then no duplicate forbidden execution or false terminal status
    And no duplicate forbidden execution or terminal status overwrite
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: Both; risk: High; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use disposable scoped identities and sanitized artifacts. Never mutate production providers. If the provider mutation is relevant, run only in a governed sandbox with before/after read-back and cleanup.
  @UAT-OPS-003 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OPS-003 - Worker/queue dependency unavailable or blocked
    Given known JobExecution history, policy scopes and isolated queue worker fixtures; unavailable queue/worker with historical JobExecution
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Worker/queue dependency unavailable or blocked
    And perform the scenario action using an approved browser or domain test client: Worker/queue dependency unavailable or blocked
    And attempt a new job and inspect Overview/Jobs degraded state
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-003
    Then correct blocked/degraded visibility, no invented execution success
    And no invented success and historical jobs remain attributable
    And the negative request does not create a misleading success state or an unauthorized committed/provider side effect

  # Layer: UI; risk: Medium; Newly expanded specification — capability-owner review required.
  # Evidence: browser screenshots and Playwright trace after interaction; pytest JUnit and exact request/response; JobExecution/activity audit and persisted state or relevant normalized correlation.
  # Isolation: Use deterministic isolated fixtures and restore modified UI/session state; record expected unavailable/empty states without inventing provider data.
  @UAT-OPS-004 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OPS-004 - Platform Overview and Jobs tabs/filters/actions are exercised
    Given known JobExecution history, policy scopes and isolated queue worker fixtures; committed Platform summary and permission-scoped jobs
    And the actor permission, selected source and original state are recorded
    When record the exact candidate, actor, scoped source identity and baseline state for: Platform Overview and Jobs tabs/filters/actions are exercised
    And perform the scenario action using an approved browser or domain test client: Platform Overview and Jobs tabs/filters/actions are exercised
    And filter overview/jobs then switch to restricted mobile actor
    And inspect the resulting UI or API state, committed KAORI state and authoritative evidence for UAT-OPS-004
    Then committed-only summary, appropriate permission scopes and canonical visual states
    And committed summary and action visibility obey RBAC
    And the observed success is attributable to the selected source, authorized actor and correct committed identity

