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

  # Layer: UI; risk: Medium; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-005 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OPS-005 - Operations Overview presents committed workspace posture in compact cards
    Given an authorized operator can view Jobs, Data Lifecycle and Kubernetes Administration from committed KAORI state
    When the operator opens Operations Center Overview and compares the three workspace cards and Platform Posture Hero
    Then three permissioned workspace cards show canonical domain status, three evidence metrics, compact one-line descriptions and source-owned navigation with a matching overall review posture
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: UI; risk: Medium; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-006 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OPS-006 - Jobs configuration catalog and schedule controls retain operational context
    Given a permitted Jobs operator and the registered 19-job configuration catalog with known committed schedules
    When the operator searches and selects Jobs, reviews schedule policy and execution details, then uses the compact catalog footer Guide
    Then the selected job follows the URL and HTMX navigation, search count updates, schedule controls and one-line Scope remain aligned, and the Guide opens above the footer without a horizontal scrollbar
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: UI; risk: Medium; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-007 @positive @medium @ui @specified @owner_review
  Scenario: UAT-OPS-007 - Report dispatcher shows compact committed delivery channels
    Given a permitted Reports Schedule Dispatcher operator and known configured committed notification channels
    When the operator views Delivery Channels with zero, one or multiple selected channels and inspects their status labels
    Then the bounded keyboard-scrollable channel rows show names, statuses, singular or plural count and an explicit empty state without oversized cards or additional provider requests
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: UI; risk: High; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-008 @positive @high @ui @specified @owner_review
  Scenario: UAT-OPS-008 - Guarded empty-inventory recovery guidance stays adjacent and manual
    Given a permitted operator views Object Storage or Artifact Registry Job Configuration in a safe non-mutating session
    When the operator reads each Guarded Recovery title, opens its canonical Guide and examines target selectors and confirmation controls without submitting
    Then shared Violet cards retain the manual-only warning and full fail-closed Guide beside the title; the CONFIRM EMPTY challenge, CSRF and verification action remain identifiable but unexecuted
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: Both; risk: High; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-009 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OPS-009 - Overview reflects scheduler policy dispatch failure without an execution
    Given a disposable committed JobPolicy with failed or evidence_failed dispatch status and no matching JobExecution
    When a permitted actor opens Overview and Jobs Configuration for that state
    Then Jobs posture is Needs Attention and the policy attention remains visible without fabricating completed or active executions; only persisted read models are queried
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: Both; risk: High; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-010 @negative @high @ui @non_ui @specified @owner_review
  Scenario: UAT-OPS-010 - Restricted role cannot reach unauthorized Operations Overview content
    Given synthetic principals with jobs.configure only, jobs.view only and mixed access without unrelated permissions
    When each principal requests the Overview URL directly, follows permitted Welcome shortcut and inspects Operating Boundaries
    Then configure-only access does not grant Overview, view-only and mixed roles see only permitted workspace cards and links, and no restricted data or actions leak
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: Non-UI; risk: High; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-011 @negative @high @non_ui @specified @owner_review
  Scenario: UAT-OPS-011 - Guarded reconciliation fails closed on mismatched provider discovery
    Given an isolated eligible Storage or Registry instance with a last-good committed inventory and intentionally mismatched first and second discovery results
    When a properly authorized disposable test actor submits CONFIRM EMPTY with the required CSRF token
    Then provider mismatch or changed snapshot rejects reconciliation and preserves the committed inventory without deleting records or claiming success
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

  # Layer: UI; risk: Medium; authority #3115 / #1738; human evidence is issue-bound.
  # Machine Scenario-ID execution NOT RUN. Disabled/provider actions require admitted isolated fixture.
  @UAT-OPS-012 @negative @medium @ui @specified @owner_review
  Scenario: UAT-OPS-012 - Unfinished feature-cycle controls remain transparently unavailable
    Given a Jobs Configuration capability whose action is intentionally disabled until its owning feature implementation finishes
    When the operator inspects the disabled action, readiness text and execution history without trying to bypass the server boundary
    Then disabled status remains truthful, the UI does not imply a completed or executable capability, and no mutation or fake success is recorded
    And record the candidate SHA, operator role, sanitized screenshot/test result and committed evidence without inventing provider success

